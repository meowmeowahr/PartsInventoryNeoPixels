import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger
import yaml
import traceback
import sys
import threading

try:
    import board
    import neopixel
except NotImplementedError as e:
    logger.error(f"Error importing NeoPixel driver {repr(e)}. If you are using the emulator, you can ignore this message.")
import neopixel_emu

import animator

# Import yaml config
with open("config.yaml", encoding="utf-8") as stream:
    try:
        configuration: dict = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        traceback.print_exc()
        logger.critical("YAML Parsing Error, %s", exc)
        sys.exit(0)

if not configuration:
    configuration: dict = {}

# logging config
logging_config: dict = configuration.get("logging", {})
logging_level: int = logging_config.get("level", 20)
logger.remove()
logger.add(sys.stdout, level=logging_level)

# server config
server_config: dict = configuration.get("server", {})
server_port: int = int(server_config.get("ip", 4300))
server_host: str = str(server_config.get("host", "127.0.0.1"))

# neopixel driver
driver_config: dict = configuration.get("driver", {})

virtual: bool = driver_config.get("virtual", False)
num_pixels: int = driver_config.get("num_pixels", 100)  # strip length
if not virtual:
    if "board" not in locals():
        logger.critical("board module was not imported. If you want to use emulated neopixels, make sure the enable the \"virtual\" option under the \"driver\" config.")
        sys.exit()
    pixel_pin = getattr(board, driver_config.get("pin", "D18"))  # rpi gpio pin
else:
    pixel_pin = None
pixel_order = driver_config.get("order", "RGB")  # Color order

# TODO: Un hardcode these values
led_indexes = {
    "A1": 0,
    "A2": 1,
    "A3": 2,
    "A4": 3,
    "A5": 4,
    "A6": 5,
    "B1": 6,
    "B2": 7,
    "B3": 8,
    "B4": 9,
}

# Create NeoPixel object

animation_args = animator.AnimationArgs()
animation_args.single_color.color = (0, 255, 0)

animation_state = animator.AnimationState()
animation_state.brightness = 100

if virtual:
    pixels = neopixel_emu.NeoPixel(
        pixel_pin, num_pixels, brightness=1.0, auto_write=False, pixel_order=pixel_order
    )
else:
    pixels = neopixel.NeoPixel(
        pixel_pin, num_pixels, brightness=1.0, auto_write=False, pixel_order=pixel_order # type: ignore
    )
animator_engine = animator.Animator(pixels, num_pixels, animation_state, animation_args)

class PartIdentify(BaseModel):
    location: str

app = FastAPI()

origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def attempt_get_led_index(location: str) -> int:
    if location in led_indexes.keys():
        return led_indexes[location]
    else:
        return 0

@app.post("/identify")
async def identify(body: PartIdentify):
    animation_args.identify.index = attempt_get_led_index(body.location)
    if not animation_state.effect == "Identify":
        old_state = animation_state.state
        old_effect = animation_state.effect
        animation_state.state = "ON"
        animation_state.effect = "Identify"
        await asyncio.sleep(2)
        animation_state.state = old_state
        animation_state.effect = old_effect

def animator_cycler():
    while True:
        animator_engine.cycle()

if __name__ == "__main__":
    import uvicorn

    threading.Thread(
        target=animator_cycler, name="AnimatorCycler", daemon=True
    ).start()

    uvicorn.run(app, host=server_host, port=server_port)
