#!/usr/bin/env python3
import dbus
import dbus.types
import os
from typing import BinaryIO
from gi.repository import GLib
from dbus.mainloop.glib import DBusGMainLoop

DBusGMainLoop(set_as_default=True)
session_bus = dbus.SessionBus()
system_bus = dbus.SystemBus()

policyAgent = dbus.Interface(
	session_bus.get_object(
		bus_name='org.kde.Solid.PowerManagement.PolicyAgent',
		object_path='/org/kde/Solid/PowerManagement/PolicyAgent'
	),
	dbus_interface='org.kde.Solid.PowerManagement.PolicyAgent'
)

manager = dbus.Interface(
	system_bus.get_object(
		bus_name='org.freedesktop.login1',
		object_path='/org/freedesktop/login1'
	),
	dbus_interface='org.freedesktop.login1.Manager'
)

inhibit_fd: dbus.types.UnixFd = None
what = 'handle-lid-switch:sleep'
who = os.getlogin()
why = 'Block lid switch when a sleep inhibit is active'
mode = 'block'

def create_inhibit() -> None:
	global inhibit_fd
	if not inhibit_fd:
		inhibit_fd = manager.Inhibit(what, who, why, mode)
		print('Inhibited. Descriptor:', inhibit_fd)

def release_inhibit() -> None:
	global inhibit_fd
	if inhibit_fd:
		os.close(inhibit_fd.take())
		inhibit_fd = None
		print('Inhibit released')

def signal_handler(*args) -> None:
	inhibitors: dbus.types.Array = policyAgent.ListInhibitions()
	if any(inhibitor[0] == 'org.kde.plasmashell' for inhibitor in inhibitors):
		create_inhibit()
	else:
		release_inhibit()


def main() -> None:
	session_bus.add_signal_receiver(
		handler_function=signal_handler,
		dbus_interface='org.kde.Solid.PowerManagement.PolicyAgent',
		path='/org/kde/Solid/PowerManagement/PolicyAgent',
		signal_name='InhibitionsChanged',
	)

	loop = GLib.MainLoop()
	loop.run()

if __name__ == '__main__':
	main()
