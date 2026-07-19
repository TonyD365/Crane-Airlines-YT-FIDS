#!/usr/bin/env python3
"""演示文本自动换行功能"""

from datetime import datetime, timezone
from crane_fids import Flight, FlightStatus
from crane_fids.renderer import FidsRenderer, FrameContext
from crane_fids.renderer.theme import Layout
from crane_fids.config import Config

# 创建配置
config = Config.from_env({"WIDTH": "1920", "HEIGHT": "1080", "FPS": "30"})

# 创建渲染器
renderer = FidsRenderer.from_config(config)

# 创建测试航班 - 包含长文本
now = datetime.now(timezone.utc)
flights = [
    Flight(
        "CR101",
        "NEW YORK",
        now,
        "A12",
        FlightStatus.ON_TIME,
        departure="NEWARK"
    ),
    Flight(
        "CR102",
        "BEIJING CAPITAL INTERNATIONAL AIRPORT",  # 长文本
        now,
        "B08",
        FlightStatus.EC_BOARDING,
        departure="BEIJING"
    ),
    Flight(
        "CR103",
        "LOS ANGELES INTERNATIONAL AIRPORT",  # 长文本
        now,
        "C11",
        FlightStatus.GATE_OPEN,
        departure="LOS ANGELES"
    ),
    Flight(
        "CR104",
        "TOKYO",  # 短文本
        now,
        "D09",
        FlightStatus.EC_BOARDING,
        departure="TOKYO"
    ),
]

# 创建帧上下文
ctx = FrameContext(
    now=now,
    frame_index=0,
    fps=30,
    flights=tuple(flights),
    airline_name="CRANE AIRLINES",
    airport_name="CRANE INTERNATIONAL AIRPORT",
    board_title="DEPARTURES",
    ticker_text="WELCOME TO CRANE INTERNATIONAL AIRPORT",
    timezone_label="LOCAL TIME",
    rows_per_page=10,
    page_seconds=15,
)

# 渲染帧
image = renderer.render(ctx)

# 保存预览图
output_path = "text_wrap_preview.png"
image.save(output_path)

print(f"✅ 预览图已保存到: {output_path}")
print(f"   图像大小: {image.size}")
print(f"   航班数量: {len(flights)}")
print()
print("测试航班:")
for i, flight in enumerate(flights, 1):
    print(f"{i}. {flight.flight_number} - {flight.destination}")
    print(f"   状态: {flight.status.label}")
    print(f"   登机口: {flight.gate}")
    print()

print("说明:")
print("- CR102 和 CR103 的目的地文本较长，应该会自动换行并占用两行高度")
print("- CR101 和 CR104 的文本较短，应该只占用一行高度")
print("- 查看生成的图片确认自动换行效果")