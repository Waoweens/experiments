#!/usr/bin/env python3
# Bad Apple!! but with nested Wayland compositors
# why use a graphics library when you can spawn a window manager for every pixel?
# IMPORTANT: SCREEN LOCKING MUST BE BLOCKED
# NOTE: may add unexpected system tray entries
#       on my system, my tray got filled with Fcitx5 buttons
#       they will eventually disappear after the script ends
# NOTE: this will stress your computer, even after the script ends,
#       as the system tries to clean up everything!

# image source: https://archive.org/details/bad_apple_is.7z
# downscaled with imagemagick to 20x15

# to disable window decorations, create a window rule:
# Window Title: Match substring "KDE Wayland Compositor"
# Property: No titlebar and frame

import os
import subprocess
import time
import dbus
import concurrent.futures
from PIL import Image

parent_size = [640, 480]
pixel_size = 32 # 20x15 @ 640x480
test_frame = 'badapple/ba-20x15-test.png' # 20x15 @ 640x480
# pixel_size 16 # 40x30 @ 640x480
#test_frame = 'badapple/ba-40x30-test.png' # 40x30 @ 640x480

def create_compositor(index, pixel_size, environment):
	environment['WAYLAND_DISPLAY'] = 'badapple-parent'
	child = subprocess.Popen(['kwin_wayland','--socket', f'badapple-{str(index)}', '--width', str(pixel_size), '--height', str(pixel_size)], env=environment)
	return child.pid

def move_window(proxy, index, pid, x, y):
	with open(f'/tmp/badapple-move-{str(index)}.js', 'w') as f:
		f.write(f'workspace.windowList().some(client => client.pid === {pid} ? ((client.frameGeometry = {{x:{x}, y:{y}, width:client.width, height: client.height}}), true) : false);')
	proxy.loadScript(f'/tmp/badapple-move-{str(index)}.js')
	proxy.start()

def move_windows(proxy, pids, pixel_size):
	with concurrent.futures.ThreadPoolExecutor() as executor:
		futures = []
		for i, pid in enumerate(pids):
			new_x = pixel_size * (i % 20)
			new_y = pixel_size * (i // 20)
			futures.append(executor.submit(move_window, proxy, (i + 1), pid, new_x, new_y))

		concurrent.futures.wait(futures)

def set_pixel(environment, index, color):
	environment['WAYLAND_DISPLAY'] = f'badapple-{str(index)}'
	# if true, color is FFFFFF, else 000000
	color_code = 'FFFFFF' if color else '000000'
	subprocess.Popen(['swaybg', '-c', color_code, '-m', 'solid_color'], env=environment)

def set_frame(environment, frame):
	# set color for all windows
	with concurrent.futures.ThreadPoolExecutor() as executor:
		futures = [
			executor.submit(set_pixel, environment.copy(), (index + 1), color)
			for index, color in enumerate(frame)
		]
		concurrent.futures.wait(futures)

def image_to_frame(image_path):
	img = Image.open(image_path)
	if img.mode != '1':
		img = img.convert('1')
	return [1 if pixel == 255 else 0 for pixel in list(img.getdata())]

def main():
	global parent_size, pixel_size, test_frame
	environment = os.environ.copy()
	pixel_count = (parent_size[0] // pixel_size) * (parent_size[1] // pixel_size)

	# start a new dbus session and set the environment variables
	# equivalent of `export $(dbus-launch)`
	dbus_session = subprocess.check_output(['dbus-launch'], text=True)
	for env in list(filter(None, dbus_session.split('\n'))):
		key, value = env.split('=', 1)
		environment[key] = value
		os.environ[key] = value

	bus = dbus.SessionBus()

	parent = subprocess.Popen(['kwin_wayland','--socket', 'badapple-parent', '--width', str(parent_size[0]), '--height', str(parent_size[1])], env=environment)
	parent_pid = parent.pid
	time.sleep(0.5)
	environment['WAYLAND_DISPLAY'] = 'badapple-parent'
	subprocess.Popen(['swaybg', '-c', 'FF0000', '-m', 'solid_color'], env=environment)
	time.sleep(0.5)

	print('Starting child compositors')
	kwin_script = bus.get_object('org.kde.KWin', '/Scripting')
	environment['QT_QPA_PLATFORM'] = 'wayland'

	print('Creating compositors')
	pids = []
	for i in range(1, pixel_count + 1):
		pid = create_compositor(i, pixel_size, environment.copy())
		pids.append(pid)
		time.sleep(0.05)
	
	time.sleep(2)
	print('Moving windows')
	move_windows(kwin_script, pids, pixel_size)

	time.sleep(0.5)

	# test frame
	frame = [1] * pixel_count
	set_frame(environment, frame)
	time.sleep(2)

	# test image
	# open an image and read pixel data
	frame = image_to_frame(test_frame)
	set_frame(environment, frame)

	print(pids)

if __name__ == '__main__':
	main()
	