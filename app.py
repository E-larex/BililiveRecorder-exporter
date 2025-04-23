from flask import Flask, Response
import requests
from requests.auth import HTTPBasicAuth
import os


try:
    api_url = os.getenv('API_URL', 'http://127.0.0.1:2356/api/room')
    auth_user = os.getenv('API_USER', 'admin')
    auth_pass = os.getenv('API_PASS', 'admin')
except:
    pass

app = Flask(__name__)

def escape_label_value(value):
    """转义Prometheus标签值中的特殊字符（兼容Unicode）"""
    return str(value).translate(str.maketrans({
        "\\": r"\\",
        '"': r'\"',
        '\n': r'\n'
    }))

@app.route('/metrics')
def export_metrics():
    try:
        resp = requests.get(
            api_url,
            auth=HTTPBasicAuth(auth_user, auth_pass),
            timeout=5
        )
        resp.encoding = 'utf-8'  # 强制设置响应编码
        resp.raise_for_status()
        rooms = resp.json()

        metrics = []
        for room in rooms:
            labels = {
                "roomId": escape_label_value(room.get("roomId", "")),
                "name": escape_label_value(room.get("name", "")),
                "uid": escape_label_value(room.get("uid", "")),
                "areaParent": escape_label_value(room.get("areaNameParent", "")),
                "areaChild": escape_label_value(room.get("areaNameChild", ""))
            }
            value = 1 if room.get("streaming", False) else 0
            labels_str = ",".join([f'{k}="{v}"' for k, v in labels.items()])
            metrics.append(f"bilibili_room_streaming_status{{{labels_str}}} {value}")

        # 使用Response对象并明确设置编码
        return Response(
            "\n".join(metrics),
            mimetype="text/plain; version=0.0.4; charset=utf-8"
        )

    except Exception as e:
        return Response(
            f"Error: {str(e)}",
            status=500,
            mimetype="text/plain; charset=utf-8"
        )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)