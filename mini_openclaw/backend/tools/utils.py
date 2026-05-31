"""实用工具集合"""
import json
import os
import platform
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List


def register_utils_tools(registry, agent):
    """注册实用工具"""

    # 网络工具
    def network_ping(args: Dict) -> Dict:
        """Ping 测试"""
        host = args.get("host", "8.8.8.8")
        count = args.get("count", 4)
        try:
            import subprocess
            param = "-n" if platform.system().lower() == "windows" else "-c"
            result = subprocess.run(
                ["ping", param, str(count), host],
                capture_output=True, text=True, timeout=30
            )
            return {
                "success": result.returncode == 0,
                "host": host,
                "output": result.stdout,
                "error_output": result.stderr if result.stderr else None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def network_info(args: Dict) -> Dict:
        """获取网络信息"""
        try:
            import socket
            import psutil
            interfaces = []
            for name, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        interfaces.append({
                            "name": name,
                            "ip": addr.address,
                            "netmask": addr.netmask
                        })

            # 获取公网 IP
            public_ip = "unknown"
            try:
                import requests
                public_ip = requests.get("https://api.ipify.org", timeout=5).text
            except:
                pass

            return {
                "success": True,
                "hostname": socket.gethostname(),
                "interfaces": interfaces,
                "public_ip": public_ip
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # 进程管理
    def process_list(args: Dict) -> Dict:
        """列出系统进程"""
        try:
            import psutil
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
                try:
                    info = proc.info
                    if info['cpu_percent'] and info['cpu_percent'] > 0:
                        processes.append(info)
                except:
                    pass

            # 按 CPU 排序，取前 20
            processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)

            return {
                "success": True,
                "processes": processes[:20],
                "total": len(list(psutil.process_iter()))
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def process_kill(args: Dict) -> Dict:
        """结束进程"""
        pid = args.get("pid")
        if not pid:
            return {"success": False, "error": "请提供进程 PID"}
        try:
            import psutil
            p = psutil.Process(int(pid))
            name = p.name()
            p.terminate()
            return {"success": True, "pid": pid, "name": name, "message": f"进程 {name} (PID: {pid}) 已终止"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # 编码/解码工具
    def encode_base64(args: Dict) -> Dict:
        """Base64 编码"""
        import base64
        text = args.get("text", "")
        try:
            encoded = base64.b64encode(text.encode()).decode()
            return {"success": True, "original": text, "encoded": encoded}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def decode_base64(args: Dict) -> Dict:
        """Base64 解码"""
        import base64
        text = args.get("text", "")
        try:
            decoded = base64.b64decode(text.encode()).decode()
            return {"success": True, "original": text, "decoded": decoded}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def hash_text(args: Dict) -> Dict:
        """文本哈希"""
        import hashlib
        text = args.get("text", "")
        algorithm = args.get("algorithm", "md5")
        try:
            if algorithm == "md5":
                result = hashlib.md5(text.encode()).hexdigest()
            elif algorithm == "sha1":
                result = hashlib.sha1(text.encode()).hexdigest()
            elif algorithm == "sha256":
                result = hashlib.sha256(text.encode()).hexdigest()
            else:
                return {"success": False, "error": "不支持的算法，可选: md5, sha1, sha256"}
            return {"success": True, "text": text, "algorithm": algorithm, "hash": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # URL 工具
    def url_parse(args: Dict) -> Dict:
        """解析 URL"""
        from urllib.parse import urlparse, parse_qs
        url = args.get("url", "")
        try:
            parsed = urlparse(url)
            return {
                "success": True,
                "scheme": parsed.scheme,
                "netloc": parsed.netloc,
                "path": parsed.path,
                "params": parsed.params,
                "query": parse_qs(parsed.query),
                "fragment": parsed.fragment
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # 二维码生成
    def generate_qrcode(args: Dict) -> Dict:
        """生成二维码"""
        text = args.get("text", "")
        try:
            import qrcode
            from io import BytesIO
            import base64

            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(text)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            img_str = base64.b64encode(buffer.getvalue()).decode()

            return {
                "success": True,
                "text": text,
                "image_base64": img_str,
                "data_url": f"data:image/png;base64,{img_str}"
            }
        except ImportError:
            return {"success": False, "error": "请先安装 qrcode: pip install qrcode[pil]"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # 注册所有工具
    registry.register("network_ping", "Ping 测试网络连通性",
        {"host": {"type": "string", "description": "目标主机", "default": "8.8.8.8"},
         "count": {"type": "integer", "description": "发送次数", "default": 4}},
        network_ping)

    registry.register("network_info", "获取本机网络信息", {}, network_info)

    registry.register("process_list", "列出系统进程（按CPU排序）", {}, process_list)

    registry.register("process_kill", "结束指定进程",
        {"pid": {"type": "integer", "description": "进程 PID"}},
        process_kill)

    registry.register("encode_base64", "Base64 编码",
        {"text": {"type": "string", "description": "要编码的文本"}},
        encode_base64)

    registry.register("decode_base64", "Base64 解码",
        {"text": {"type": "string", "description": "要解码的文本"}},
        decode_base64)

    registry.register("hash_text", "文本哈希",
        {"text": {"type": "string", "description": "要哈希的文本"},
         "algorithm": {"type": "string", "description": "算法: md5/sha1/sha256", "default": "md5"}},
        hash_text)

    registry.register("url_parse", "解析 URL",
        {"url": {"type": "string", "description": "要解析的 URL"}},
        url_parse)

    registry.register("generate_qrcode", "生成二维码",
        {"text": {"type": "string", "description": "二维码内容"}},
        generate_qrcode)
