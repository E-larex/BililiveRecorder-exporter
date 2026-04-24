# BililiveRecorder-exporter

## 这是什么？

通过 [BililiveRecorder](https://github.com/BililiveRecorder/BililiveRecorder) 的API，将直播间信息转为 Prometheus 的时序数据格式，使 Prometheus 能够记录直播间状态。  
同时包括了一个 [Grafana](./grafana/Bilibili%20Live.json) 面板，能够直观的了解到各个直播间的直播状态。

## 配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `API_URL` | `http://127.0.0.1:2356/api/room` | BililiveRecorder 的直播间 API 地址 |
| `API_USER` | `admin` | API Basic Auth 用户名 |
| `API_PASS` | `admin` | API Basic Auth 密码 |
| `API_TIMEOUT` | `5` | 请求 BililiveRecorder API 的超时时间，单位秒 |
| `PORT` | `5000` | 直接运行 `python app.py` 时监听的端口 |

## 指标

Exporter 会保留原有的 `bilibili_room_streaming_status`，并补充导出 BililiveRecorder `2.18.0` `/api/room` 返回的主要字段：

- 房间信息：`bilibili_room_info`
- 当前 IO 流信息：`bilibili_room_io_info`
- 房间状态：`bilibili_room_streaming_status`、`bilibili_room_recording_status`、`bilibili_room_auto_record_status`、`bilibili_room_danmaku_connected_status`、`bilibili_room_auto_record_for_this_session_status`
- 录制统计：`bilibili_room_recording_*`
- IO 统计：`bilibili_room_io_*`

所有状态和统计值都按 gauge 导出，因为 BililiveRecorder 的会话统计会在录制结束或新会话开始时归零。
