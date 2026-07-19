#!/usr/bin/env python3
"""测试超长文本换行（超过2行）"""

from datetime import datetime, timezone
from crane_fids import Flight, FlightStatus
from crane_fids.renderer import FidsRenderer, FrameContext
from crane_fids.config import Config

# 创建配置
config = Config.from_env({"WIDTH": "1920", "HEIGHT": "1080", "FPS": "30"})
renderer = FidsRenderer.from_config(config)

now = datetime.now(timezone.utc)

# 创建超长文本的测试航班
flights = [
    Flight(
        "CR101",
        "NEW YORK",  # 短文本
        now,
        "A12",
        FlightStatus.ON_TIME,
        departure="NEWARK"
    ),
    Flight(
        "CR102",
        "BEIJING CAPITAL INTERNATIONAL AIRPORT TERMINAL 3",  # 超长文本
        now,
        "B08",
        FlightStatus.EC_BOARDING,
        departure="BEIJING"
    ),
    Flight(
        "CR103",
        "LOS ANGELES INTERNATIONAL AIRPORT",  # 中等长度
        now,
        "C11",
        FlightStatus.GATE_OPEN,
        departure="LOS ANGELES"
    ),
    Flight(
        "CR104",
        "A",  # 极短
        now,
        "D09",
        FlightStatus.EC_BOARDING,
        departure="TOKYO"
    ),
]

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

image = renderer.render(ctx)
image.save("long_text_preview.png")

print("✅ 预览图已保存到: long_text_preview.png")
print()
print("测试航班（包含超长文本）:")
for i, flight in enumerate(flights, 1):
    print(f"{i}. {flight.flight_number} - {flight.destination}")
    print(f"   文本长度: {len(flight.destination)} 字符")
print()
print("说明:")
print("- CR102 的文本很长，应该会分成3行或更多")
print("- CR103 的文本中等长度，应该会分成2行")
print("- CR101 和 CR104 保持单行")
print("- 查看图片确认多行换行效果")