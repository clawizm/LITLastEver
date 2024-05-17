import socket
import led_manager_with_classes
from led_manager_with_classes import LEDPanels
import time
import board
import neopixel
import math
import server_with_classes
from server_with_classes import LITSubsystemServer
import threading
from multiprocessing import Process


if __name__ == '__main__':
    subsystem_panels_one = LEDPanels(board.D18)
    subsystem_panels_two = LEDPanels(board.D21)
    subsystem_panel_one_server = LITSubsystemServer(subsystem_panels_one, 5000)
    subsystem_panel_two_server = LITSubsystemServer(subsystem_panels_two, 5001)

    
    server_with_classes.run_lit_subsystem_servers_in_parallel([subsystem_panel_one_server, subsystem_panel_two_server])


#I CAN STORE DATA INVOLVING MAUNALLY CONTROLLING THE LEDS, SUCH AS THE CURRENT MANUALLY LED RANGES AND THEIR BRIGHTNESS FOR EACH SUBSYSTEM 
