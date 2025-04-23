# BililiveRecorder-exporter

## 这是什么？

通过 [BililiveRecorder](https://github.com/BililiveRecorder/BililiveRecorder) 的API，将直播间信息转为 Prometheus 的时序数据格式，使 Prometheus 能够记录直播间状态。  
同时包括了一个 [Grafana](./grafana/Bilibili%20Live.json) 面板，能够直观的了解到各个直播间的直播状态。