from datetime import datetime, timezone
import math
import os

from flask import Flask, Response
import requests
from requests.auth import HTTPBasicAuth


api_url = os.getenv("API_URL", "http://127.0.0.1:2356/api/room")
auth_user = os.getenv("API_USER", "admin")
auth_pass = os.getenv("API_PASS", "admin")
request_timeout = float(os.getenv("API_TIMEOUT", "5"))

app = Flask(__name__)


STATUS_METRICS = (
    ("streaming", "bilibili_room_streaming_status", "Whether the room is currently streaming."),
    ("recording", "bilibili_room_recording_status", "Whether BililiveRecorder is currently recording the room."),
    ("autoRecord", "bilibili_room_auto_record_status", "Whether automatic recording is enabled for the room."),
    ("danmakuConnected", "bilibili_room_danmaku_connected_status", "Whether the danmaku connection is established."),
    (
        "autoRecordForThisSession",
        "bilibili_room_auto_record_for_this_session_status",
        "Whether automatic recording is enabled for the current live session.",
    ),
)

RECORDING_STATS_METRICS = (
    ("sessionDuration", "bilibili_room_recording_session_duration_milliseconds", "Time elapsed since recording started."),
    ("totalInputBytes", "bilibili_room_recording_total_input_bytes", "Total received bytes in the current session."),
    ("totalOutputBytes", "bilibili_room_recording_total_output_bytes", "Total written bytes in the current session."),
    ("currentFileSize", "bilibili_room_recording_current_file_size_bytes", "Current recording file size."),
    (
        "sessionMaxTimestamp",
        "bilibili_room_recording_session_max_timestamp_milliseconds",
        "Maximum fixed stream timestamp in the current session.",
    ),
    (
        "fileMaxTimestamp",
        "bilibili_room_recording_file_max_timestamp_milliseconds",
        "Maximum fixed stream timestamp in the current file.",
    ),
    ("addedDuration", "bilibili_room_recording_added_duration_milliseconds", "Stream duration added in the current stats interval."),
    ("passedTime", "bilibili_room_recording_passed_time_milliseconds", "Wall time passed in the current stats interval."),
    ("durationRatio", "bilibili_room_recording_duration_ratio", "Recording speed ratio."),
    ("inputVideoBytes", "bilibili_room_recording_input_video_bytes", "Video bytes received in the current stats interval."),
    ("inputAudioBytes", "bilibili_room_recording_input_audio_bytes", "Audio bytes received in the current stats interval."),
    ("outputVideoFrames", "bilibili_room_recording_output_video_frames", "Video frames written in the current stats interval."),
    ("outputAudioFrames", "bilibili_room_recording_output_audio_frames", "Audio frames written in the current stats interval."),
    ("outputVideoBytes", "bilibili_room_recording_output_video_bytes", "Video bytes written in the current stats interval."),
    ("outputAudioBytes", "bilibili_room_recording_output_audio_bytes", "Audio bytes written in the current stats interval."),
    ("totalInputVideoBytes", "bilibili_room_recording_total_input_video_bytes", "Total video bytes received in the current session."),
    ("totalInputAudioBytes", "bilibili_room_recording_total_input_audio_bytes", "Total audio bytes received in the current session."),
    ("totalOutputVideoFrames", "bilibili_room_recording_total_output_video_frames", "Total video frames written in the current session."),
    ("totalOutputAudioFrames", "bilibili_room_recording_total_output_audio_frames", "Total audio frames written in the current session."),
    ("totalOutputVideoBytes", "bilibili_room_recording_total_output_video_bytes", "Total video bytes written in the current session."),
    ("totalOutputAudioBytes", "bilibili_room_recording_total_output_audio_bytes", "Total audio bytes written in the current session."),
)

IO_STATS_METRICS = (
    ("duration", "bilibili_room_io_duration_milliseconds", "Duration of the current IO stats interval."),
    ("networkBytesDownloaded", "bilibili_room_io_network_bytes_downloaded", "Bytes downloaded in the current IO stats interval."),
    ("networkMbps", "bilibili_room_io_network_mibibits_per_second", "Average download speed in mebibits per second."),
    ("diskWriteDuration", "bilibili_room_io_disk_write_duration_milliseconds", "Disk write time in the current IO stats interval."),
    ("diskBytesWritten", "bilibili_room_io_disk_bytes_written", "Bytes written to disk in the current IO stats interval."),
    ("diskMBps", "bilibili_room_io_disk_mibibytes_per_second", "Average disk write speed in mebibytes per second."),
)

TIME_METRICS = (
    ("startTime", "bilibili_room_io_start_time_seconds", "Start time of the current IO stats interval."),
    ("endTime", "bilibili_room_io_end_time_seconds", "End time of the current IO stats interval."),
)


def escape_label_value(value):
    """转义 Prometheus 标签值中的特殊字符（兼容 Unicode）"""
    return str(value if value is not None else "").translate(
        str.maketrans({
            "\\": r"\\",
            '"': r"\"",
            "\n": r"\n",
        })
    )


def format_labels(labels):
    return ",".join(f'{key}="{escape_label_value(value)}"' for key, value in labels.items())


def format_metric(name, labels, value):
    return f"{name}{{{format_labels(labels)}}} {value}"


def format_prometheus_number(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            if math.isnan(value):
                return "NaN"
            if math.isinf(value):
                return "+Inf" if value > 0 else "-Inf"
        return str(value)

    value_text = str(value)
    if value_text.lower() == "nan":
        return "NaN"
    try:
        number = float(value_text)
    except ValueError:
        return None
    if math.isnan(number):
        return "NaN"
    if math.isinf(number):
        return "+Inf" if number > 0 else "-Inf"
    return value_text


def parse_datetime_seconds(value):
    if not value or str(value).startswith("0001-01-01"):
        return "0"

    value_text = str(value)
    if value_text.endswith("Z"):
        value_text = f"{value_text[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(value_text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return format_prometheus_number(parsed.timestamp())


def base_room_labels(room):
    return {
        "roomId": room.get("roomId", ""),
        "name": room.get("name", ""),
        "uid": room.get("uid", ""),
        "areaParent": room.get("areaNameParent", ""),
        "areaChild": room.get("areaNameChild", ""),
    }


def room_info_labels(room):
    labels = base_room_labels(room)
    labels.update({
        "objectId": room.get("objectId", ""),
        "shortId": room.get("shortId", ""),
        "title": room.get("title", ""),
    })
    return labels


def append_metric_definitions(metrics, emitted_definitions, name, help_text, metric_type="gauge"):
    if name in emitted_definitions:
        return
    metrics.append(f"# HELP {name} {help_text}")
    metrics.append(f"# TYPE {name} {metric_type}")
    emitted_definitions.add(name)


def append_gauge(metrics, emitted_definitions, name, help_text, labels, value):
    prometheus_value = format_prometheus_number(value)
    if prometheus_value is None:
        return
    append_metric_definitions(metrics, emitted_definitions, name, help_text)
    metrics.append(format_metric(name, labels, prometheus_value))


def build_metrics(rooms):
    metrics = []
    emitted_definitions = set()

    append_metric_definitions(
        metrics,
        emitted_definitions,
        "bilibili_room_info",
        "Static and descriptive metadata for a BililiveRecorder room.",
    )
    append_metric_definitions(
        metrics,
        emitted_definitions,
        "bilibili_room_io_info",
        "Descriptive metadata for the current room IO stream.",
    )

    for room in rooms:
        labels = base_room_labels(room)
        metrics.append(format_metric("bilibili_room_info", room_info_labels(room), "1"))

        for field, metric_name, help_text in STATUS_METRICS:
            append_gauge(metrics, emitted_definitions, metric_name, help_text, labels, room.get(field, False))

        recording_stats = room.get("recordingStats") or {}
        for field, metric_name, help_text in RECORDING_STATS_METRICS:
            append_gauge(metrics, emitted_definitions, metric_name, help_text, labels, recording_stats.get(field))

        io_stats = room.get("ioStats") or {}
        io_info_labels = dict(labels)
        io_info_labels["streamHost"] = io_stats.get("streamHost", "")
        metrics.append(format_metric("bilibili_room_io_info", io_info_labels, "1"))

        for field, metric_name, help_text in IO_STATS_METRICS:
            append_gauge(metrics, emitted_definitions, metric_name, help_text, labels, io_stats.get(field))

        for field, metric_name, help_text in TIME_METRICS:
            append_gauge(metrics, emitted_definitions, metric_name, help_text, labels, parse_datetime_seconds(io_stats.get(field)))

    return metrics


def fetch_rooms():
    resp = requests.get(
        api_url,
        auth=HTTPBasicAuth(auth_user, auth_pass),
        timeout=request_timeout,
    )
    resp.encoding = "utf-8"
    resp.raise_for_status()
    return resp.json()


@app.route("/metrics")
def export_metrics():
    try:
        metrics = build_metrics(fetch_rooms())

        return Response(
            "\n".join(metrics) + "\n",
            content_type="text/plain; version=0.0.4; charset=utf-8",
        )

    except Exception as e:
        return Response(
            f"Error: {str(e)}",
            status=500,
            content_type="text/plain; charset=utf-8",
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
