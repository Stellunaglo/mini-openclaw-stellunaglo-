"""文件系统浏览工具 - 安全地查看系统文件"""
import os
import json
from pathlib import Path
from typing import Dict, List


class FileSystemBrowser:
    """安全的文件系统浏览器"""

    def __init__(self, allowed_roots: List[str] = None):
        self.allowed_roots = allowed_roots or ["."]
        self.current_dir = Path(".").resolve()

    def list_directory(self, path: str = ".", max_depth: int = 1) -> Dict:
        """列出目录内容"""
        try:
            target = Path(path).resolve()

            # 安全检查
            if not self._is_allowed(target):
                return {"success": False, "error": "无权访问该路径"}

            if not target.exists():
                return {"success": False, "error": f"路径不存在: {path}"}

            if target.is_file():
                return {
                    "success": True,
                    "type": "file",
                    "name": target.name,
                    "path": str(target),
                    "size": target.stat().st_size,
                    "modified": target.stat().st_mtime
                }

            # 目录
            items = []
            try:
                for item in target.iterdir():
                    try:
                        stat = item.stat()
                        items.append({
                            "name": item.name,
                            "path": str(item),
                            "type": "dir" if item.is_dir() else "file",
                            "size": stat.st_size if item.is_file() else 0,
                            "modified": stat.st_mtime
                        })
                    except PermissionError:
                        items.append({
                            "name": item.name,
                            "path": str(item),
                            "type": "dir" if item.is_dir() else "file",
                            "size": 0,
                            "error": "权限不足"
                        })
            except PermissionError:
                return {"success": False, "error": "无权读取该目录"}

            return {
                "success": True,
                "type": "directory",
                "name": target.name,
                "path": str(target),
                "items": sorted(items, key=lambda x: (x["type"] != "dir", x["name"].lower())),
                "count": len(items)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def read_file(self, path: str, max_size: int = 100000) -> Dict:
        """读取文件内容"""
        try:
            target = Path(path).resolve()

            if not self._is_allowed(target):
                return {"success": False, "error": "无权访问该文件"}

            if not target.exists():
                return {"success": False, "error": f"文件不存在: {path}"}

            if target.is_dir():
                return {"success": False, "error": "路径是目录，不是文件"}

            size = target.stat().st_size
            if size > max_size:
                # 只读取前 max_size 字节
                with open(target, "rb") as f:
                    content = f.read(max_size).decode("utf-8", errors="replace")
                return {
                    "success": True,
                    "name": target.name,
                    "path": str(target),
                    "size": size,
                    "content": content,
                    "truncated": True,
                    "note": f"文件过大，仅显示前 {max_size} 字节"
                }

            with open(target, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            return {
                "success": True,
                "name": target.name,
                "path": str(target),
                "size": size,
                "content": content
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_file_info(self, path: str) -> Dict:
        """获取文件详细信息"""
        try:
            target = Path(path).resolve()

            if not self._is_allowed(target):
                return {"success": False, "error": "无权访问"}

            if not target.exists():
                return {"success": False, "error": "文件不存在"}

            stat = target.stat()
            return {
                "success": True,
                "name": target.name,
                "path": str(target),
                "type": "directory" if target.is_dir() else "file",
                "size": stat.st_size,
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "accessed": stat.st_atime,
                "permissions": oct(stat.st_mode)[-3:],
                "absolute": str(target.absolute())
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def search_files(self, pattern: str, root: str = ".", max_results: int = 50) -> Dict:
        """搜索文件"""
        try:
            root_path = Path(root).resolve()

            if not self._is_allowed(root_path):
                return {"success": False, "error": "无权搜索该路径"}

            results = []
            count = 0
            for item in root_path.rglob("*"):
                if count >= max_results:
                    break
                if pattern.lower() in item.name.lower():
                    try:
                        results.append({
                            "name": item.name,
                            "path": str(item),
                            "type": "dir" if item.is_dir() else "file",
                            "size": item.stat().st_size if item.is_file() else 0
                        })
                        count += 1
                    except:
                        pass

            return {
                "success": True,
                "pattern": pattern,
                "root": str(root_path),
                "results": results,
                "count": len(results),
                "truncated": count >= max_results
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _is_allowed(self, path: Path) -> bool:
        """检查路径是否在允许范围内"""
        # 禁止访问敏感目录
        forbidden = [r"C:\Windows", "/etc/shadow", "/root/.ssh", ".ssh", ".gnupg"]
        path_str = str(path)
        for f in forbidden:
            if f in path_str:
                return False
        return True


def register_fs_browser_tools(registry, agent):
    """注册文件系统浏览工具"""
    browser = FileSystemBrowser()

    registry.register(
        "fs_browse",
        "浏览文件系统目录",
        {"path": {"type": "string", "description": "目录路径，如 '.' 或 '/home'", "default": "."}},
        lambda args: browser.list_directory(args.get("path", ".")),
        required=[]
    )

    registry.register(
        "fs_read_system",
        "读取系统文件内容",
        {"path": {"type": "string", "description": "文件路径"},
         "max_size": {"type": "integer", "description": "最大读取字节数", "default": 100000}},
        lambda args: browser.read_file(args.get("path"), args.get("max_size", 100000)),
        required=["path"]
    )

    registry.register(
        "fs_info",
        "获取文件/目录详细信息",
        {"path": {"type": "string", "description": "文件或目录路径"}},
        lambda args: browser.get_file_info(args.get("path", ".")),
        required=["path"]
    )

    registry.register(
        "fs_search",
        "搜索文件",
        {"pattern": {"type": "string", "description": "文件名关键词"},
         "root": {"type": "string", "description": "搜索根目录", "default": "."},
         "max_results": {"type": "integer", "description": "最大结果数", "default": 50}},
        lambda args: browser.search_files(
            args.get("pattern", ""),
            args.get("root", "."),
            args.get("max_results", 50)
        ),
        required=["pattern"]
    )
