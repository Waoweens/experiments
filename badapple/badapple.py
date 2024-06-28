#!/usr/bin/env python3
# Bad Apple!! but with nested Wayland compositors
# why use a graphics library when you can spawn a window manager for every pixel?
# NOTE: may add unexpected system tray entries
#       on my system, my tray got filled with Fcitx5 buttons
#       they will eventually disappear after the script ends
# NOTE: this will stress your computer, even after the script ends,
#       as the system tries to clean up everything!
# NOTE: disable window decorations. create a window rule:
#         Window Title:  Match substring "KDE Wayland Compositor"
#         Property:      No titlebar and frame

# required external tools: kwin_wayland, swaybg, dbus-launch, systemd-inhibit
# required libraries: dbus-python, psutil, PyGObject, Pillow, playsound
# the rest are built-in modules included with recent-ish versions of Python

# image source: https://archive.org/details/bad_apple_is.7z
# due to the number of images, it is not included in this repository
# point below to the bad_apple_is directory containing image_sequence and bad_apple.wav:
badapple_dir = '~/Downloads/bad_apple_is/bad_apple_is'

# further configuration:
parent_size = (640, 480)
pixel_size = 32 # 20x15 @ 640x480
fps: tuple[float, int] = (29.97, 2) # [orig, play], orig / play = fps
import os
import subprocess
import time
import random
import dbus
import dbus.proxies
import concurrent.futures
import psutil
import gi
from gi.repository import GLib
from typing import List, Union
from PIL import Image
from pathlib import Path
from playsound import playsound

def inhibit_sleep() -> int:
	return subprocess.Popen(['systemd-inhibit', '--what=sleep', '--why=playing video', '--who=Bad Apple!!', '--mode=block', 'sleep', 'infinity']).pid

def release_sleep(pid: int):
	psutil.Process(pid).terminate()

def create_bus(environment: dict[str, str]) -> dbus.SessionBus:
	file = Path('/tmp/badapple-dbus')

	if not file.is_file():
		print('launching new dbus daemon')
		with open(file, 'w') as f:
			subprocess.run(['dbus-launch'], text=True, stdout=f)
		create_bus(environment)
	else:
		with open(file, 'r') as f:
			for line in f:
				key, value = line.strip().split('=', 1)
				print('found daemon:', key, value)
				environment[key] = value
				os.environ[key] = value

	return dbus.SessionBus()

def create_compositor(index: int, pixel_size: int, environment: dict[str, str]) -> int:
	environment['WAYLAND_DISPLAY'] = 'badapple-parent'
	child = subprocess.Popen(['kwin_wayland','--socket', f'badapple-{str(index)}', '--width', str(pixel_size), '--height', str(pixel_size)], env=environment, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
	return child.pid

def move_window(proxy: dbus.proxies.ProxyObject, index: int, pid: int, x: int, y: int):
	with open(f'/tmp/badapple-move-{str(index)}.js', 'w') as f:
		f.write(f'workspace.windowList().some(client => client.pid === {pid} ? ((client.frameGeometry = {{x:{x}, y:{y}, width:client.width, height: client.height}}), true) : false);')
	proxy.loadScript(f'/tmp/badapple-move-{str(index)}.js')
	proxy.start()

def move_windows(proxy: dbus.proxies.ProxyObject, pids: list[int], pixel_size: int):
	with concurrent.futures.ThreadPoolExecutor() as executor:
		futures = []
		for i, pid in enumerate(pids):
			new_x = pixel_size * (i % 20)
			new_y = pixel_size * (i // 20)
			futures.append(executor.submit(move_window, proxy, (i + 1), pid, new_x, new_y))

		concurrent.futures.wait(futures)

def frame_diff(frame1: list[bool], frame2: list[bool]) -> List[Union[bool, None]]:
	assert len(frame1) == len(frame2), 'frames must be the same size'
	return [
		None if item1 == item2 else item2
		for item1, item2 in zip(frame1, frame2)
	]

def set_pixel(environment: dict[str, str], index: int, color: bool) -> int:
	environment['WAYLAND_DISPLAY'] = f'badapple-{str(index)}'
	# if true, color is FFFFFF, else 000000
	color_code = 'FFFFFF' if color else '000000'
	return subprocess.Popen(['swaybg', '-c', color_code, '-m', 'solid_color'], env=environment, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL).pid

def set_frame(environment: dict[str, str], frame: list[bool], prev_frame: list[bool] = None):
	if prev_frame is not None:
		diff = frame_diff(prev_frame, frame)
	else:
		diff = frame

	env = environment.copy()
	with concurrent.futures.ThreadPoolExecutor() as executor:
		futures = [
			executor.submit(set_pixel, env, (index + 1), color)
			for index, color in enumerate(diff) if color is not None
		]
		for future in concurrent.futures.as_completed(futures):
			future.result()

def image_to_frame(image_path: Path) -> list[int]:
	global parent_size, pixel_size
	img = Image.open(image_path)
	img = img.convert('1')
	img = img.resize(((parent_size[0] // pixel_size), (parent_size[1] // pixel_size)), Image.Resampling.NEAREST)
	return [1 if pixel == 255 else 0 for pixel in list(img.getdata())]

def kill_stray():
	# kill any stray kwin_wayland processes in the `badapple` socket namespace
	processes = [
		proc for proc in psutil.process_iter()
		if proc.name() == 'kwin_wayland'
		and any('badapple' in arg for arg in proc.cmdline())
	]
	for process in processes:
		process.terminate()

	# kill any stray dbus processes
	dbus_def = Path('/tmp/badapple-dbus')
	dbus_val: dict[str, str] = {}
	if dbus_def.is_file():
		with open(dbus_def, 'r') as f:
			for line in f:
				key, value = line.strip().split('=', 1)
				dbus_val[key] = value
		dbus_def.unlink()
	if 'DBUS_SESSION_BUS_PID' in dbus_val:
		psutil.Process(int(dbus_val['DBUS_SESSION_BUS_PID'])).terminate()

def prepare_environment(environment: dict[str,str]):
	global parent_size, pixel_size
	pixel_count = (parent_size[0] // pixel_size) * (parent_size[1] // pixel_size)
	bus = create_bus(environment)

	parent = subprocess.Popen(['kwin_wayland','--socket', 'badapple-parent', '--width', str(parent_size[0]), '--height', str(parent_size[1])], env=environment, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
	time.sleep(0.5)
	environment['WAYLAND_DISPLAY'] = 'badapple-parent'
	subprocess.Popen(['swaybg', '-c', 'FF0000', '-m', 'solid_color'], env=environment, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
	time.sleep(0.5)

	print('Starting child compositors')
	kwin_script = bus.get_object('org.kde.KWin', '/Scripting')

	print('Creating compositors')
	pids: list[int] = []
	for i in range(1, pixel_count + 1):
		pid = create_compositor(i, pixel_size, environment.copy())
		pids.append(pid)
		time.sleep(0.05)
	time.sleep(2)

	print('Moving windows')
	move_windows(kwin_script, pids, pixel_size)
	time.sleep(0.5)

	# set everything to white to prepare swaybg
	set_frame(environment, ([1] * pixel_count))
	time.sleep(1)

def prepare_frame(environment: dict[str,str], images: list[Path]):
	global parent_size, pixel_size
	pixel_count = (parent_size[0] // pixel_size) * (parent_size[1] // pixel_size)

	set_frame(environment, ([1] * pixel_count))
	time.sleep(2)

def play(environment: dict[str,str], imgs: list[Path]):
	global fps
	prev_frame = None
	frametime = 1 / (fps[0] / fps[1])

	for img in imgs[::fps[1]]:
		start_time = time.time()
		frame = image_to_frame(img)
		set_frame(environment, frame, prev_frame)
		prev_frame = frame
		sleep_time = frametime - (time.time() - start_time)
		if sleep_time > 0:
			time.sleep(sleep_time)

def main():
	global badapple_dir
	environment = os.environ.copy()
	environment['QT_QPA_PLATFORM'] = 'wayland'
	dir_path = Path(badapple_dir).expanduser().resolve()
	is_path = dir_path / 'image_sequence'
	audio_path = dir_path / 'bad_apple.wav'
	imgs: list[Path] = [
		file for file in sorted(is_path.glob('bad_apple_*.png'), key=lambda path: int(path.stem.rsplit('_', 1)[1]))
	]

	print("Actions:")
	print("1. Create compositors and start Bad Apple!!")
	print("2. Start Bad Apple!! with existing compositors")
	print("3. Start compositors only")
	print("4. Kill stray processes")

	prompt = input('Your action? ')
	prompt = prompt.strip()
	match prompt:
		case '1':
			prepare_environment(environment)
			prepare_frame(environment, imgs)
		case '2':
			environment['WAYLAND_DISPLAY'] = 'badapple-parent'
			prepare_frame(environment, imgs)
		case '3':
			prepare_environment(environment)
			return
		case '4':
			kill_stray()
			return
		case _:
			print('I can break rules too. Goodbye.')
			exit(1)

	# READY
	input('Press enter to start Bad Apple!!')

	playsound(audio_path, block=False)
	play(environment, imgs)

	# END

if __name__ == '__main__':
	inhibitor = inhibit_sleep()
	main()
	release_sleep(inhibitor)