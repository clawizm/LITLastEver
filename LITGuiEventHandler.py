import PySimpleGUI as sg
import cv2
import numpy as np
import typing
import ObjectDetectionModel
from ObjectDetectionModel import ObjectDetectionModel
import threading
import time
import socket
import pickle
from LITSubsystemInterface import LITSubsystemData
from utils import AutoLEDData, ManualLEDData
import os

class LITGuiEventHandler:
    """A class handing events with the LITGUI class. The seperation of two allows for this class to be overwritten or manually implemented by other developers to handle their own events in the
    GUI.
    
    Instance Attributes:
    - led_tuples_dict_of_list (dict[list[tuple[int, int]]]): A dictionary where the key is the camera_idx of the current Subsystem being referenced, such as 'CAMERA_0'. The values stores
                                                            are a list of tuples containing two integers, where the integers are the start and stop values of ranges of the LEDSubsystem. 
                                                            These ranges are unqiue to each checkbox in the 'Manually Control LED Ranges Section'.

    - object_detection_model_dict (dict[str, typing.Union[ObjectDetectionModel, None]]): A dictonary where each key is a camera plus its index, such as 'CAMERA_0'.
                                                                                        Each Camera in the GUI has the option of being part of a subsystem, bus is not required. 
                                                                                        This dict will store each Camera passed to the GUI, and store whether that camera is used for performing Object Detection 
                                                                                        or is just used to view video from a webcam."""

    def __init__(self, background_images_dir: str = r'BackgroundImages'):
        """
        Instantiates all of the instance attibutes, as well as sets a list of all background image paths.

        Parameters:
        - background_images_dir (str): The path to the folder containing all of the images to use as backgrounds for the GUI.
        """
        
        self.all_background_images: list[str] = self.get_all_background_images(background_images_dir)
        self.led_tuples_dict_of_list: dict[list[tuple[int, int]]] = {}
        self.object_detection_model_dict: dict[str, ObjectDetectionModel] = {}
        self.lit_subsystem_dict: dict[str, LITSubsystemData] = {}
        self.manual_led_data: ManualLEDData = ManualLEDData()

    def get_all_background_images(self, directory: str)->list[str]:
        """Generates and returns a list of all png paths found in the provided directory.
        
        Parameters:
        - directory (str): The path to the folder containing all of the png images to store in a list."""

        dir_contents = os.listdir(directory)
        dir_contents_filtered = [os.path.join(directory, file) for file in dir_contents if file.endswith('.png')]
        return dir_contents_filtered
    
    def get_random_image_from_background_image_list(self)->str:
        """Returns a random image path from the list of background images using np.random to grab an item at a random index."""

        random_num = np.random.randint(0, len(self.all_background_images)-1)
        return self.all_background_images[random_num]

    def set_camera_of_event(self):
        """Used to find the camera index for the panel in which the event spawned from. This value is used to apply the setting changed to the correct Subsystem.
        Value is set to the event_camera Attribute."""
        self.event_camera = self.event.split('_')[1]
        return 
    
    def on_hand_gesture_detection(self):
        try:
            self.object_detection_model_dict[f'CAMERA_{self.event_camera}'].hand_gesture_recognition = self.get_value_of_element_from_event()
        except:
            pass
        return
    
    def on_autonomous_mode_event(self):
        """Handles an event in which the user has pressed the _AUTONOMOUSMODE checkbox in one of the Subsystems displayed on the GUI. This will either stop or start detection in the current subsystem based on the 
        value of the checkbox. It will also alter the status of the show feed checkbox."""


        if self.values[f'-CAMERA_{self.event_camera}_AUTONOMOUSMODE-']:            
            if self.object_detection_model_dict[f'CAMERA_{self.event_camera}']:
                self.object_detection_model_dict[f'CAMERA_{self.event_camera}'].start_detection()
            self.window[f'-CAMERA_{self.event_camera}_SHOWFEED-'].update(True, disabled=False)
            self.window[f'-CAMERA_{self.event_camera}_HANDGESTUREDETECTION-'].update(disabled=False)
        else:
            if self.object_detection_model_dict[f'CAMERA_{self.event_camera}']:
                self.object_detection_model_dict[f'CAMERA_{self.event_camera}'].stop_detection()
            self.window[f'-CAMERA_{self.event_camera}_FEED-'].update(filename=self.get_random_image_from_background_image_list(), size=(720, 405))
            self.window[f'-CAMERA_{self.event_camera}_SHOWFEED-'].update(False, disabled=True)
            self.window[f'-CAMERA_{self.event_camera}_HANDGESTUREDETECTION-'].update(disabled=True)

        if self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].client_conn:
            self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].auto_status = self.values[f'-CAMERA_{self.event_camera}_AUTONOMOUSMODE-']
            self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].send_data_for_led_addressing(False)

        return
    
    def on_show_camera_feed_event(self):
        """Handes an event in which the user has pressed the SHOWFEED checkbox in one of the Subsystems displayed on the GUI. Depending on the state of the checkbox, the videostream from the camera will either
        be passed to the GUI, or will no longer displayed. By disabling feed the performance of the System increases."""

        if self.values[f'-CAMERA_{self.event_camera}_SHOWFEED-'] and self.object_detection_model_dict[f'CAMERA_{self.event_camera}']:
            self.object_detection_model_dict[f'CAMERA_{self.event_camera}'].set_window(self.window)
        else:
            self.object_detection_model_dict[f'CAMERA_{self.event_camera}'].set_window(None)
            # time.sleep(2)
            self.window[f'-CAMERA_{self.event_camera}_FEED-'].update(filename=self.get_random_image_from_background_image_list(), size=(720, 405))
        return
    
    def on_manual_control_event(self):
        """Handles an event in which the user has altered the state of one of the MANUALSTATUS checkboxes displayed on the GUI inside one of the Subsystem Frames. If there is a connection to a server, this event will send 
        relevant manual control data to the server and update LEDs accordingly."""

        manual_status = self.values[f'-CAMERA_{self.event_camera}_MANUALSTATUS-']
        if manual_status:
            self.enable_all_manual_options_of_subsystem()
        else:
            self.disable_all_manual_options_of_subsystem()

        self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].manual_status = manual_status
        if self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].client_conn and not self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].auto_status:
            self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].send_data_for_led_addressing(True) #this breaks the other loop somehow
        else:
            # time.sleep(.25)
            self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].send_data_for_led_addressing(True)
        return
    
    def on_turn_on_all_leds(self):
        """Handles an event in which the user has altered the state of the the Turn On All LEDs checkbox displayed on the GUI. If there is a connection to a server, this event will send relevant
        manual control data to the server and update LEDs accordingly."""

        if self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].client_conn:
            self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].force_all_leds_on = self.get_value_of_element_from_event()
            if not self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].auto_status:
                self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].send_data_for_led_addressing(True)
            else:
                # time.sleep(.25)
                self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].send_data_for_led_addressing(True)


    def on_manually_control_led_range_event(self):  
        """Handles an event in which the user has altered the state of one of the LED range checkboxes displayed on the GUI inside one of the Subsystem Frames. If there is a connection to a server, this event will
        update the state of the LED range selected by the user in the physical LED Subsystem."""  
        if self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].client_conn:
            led_range = self.get_led_range_from_event()
            if self.get_value_of_element_from_event():
                self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].system_led_data.manual_led_data.add_led_range(led_range)
            else:
                self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].system_led_data.manual_led_data.remove_led_range(led_range)
            if not self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].auto_status:
                self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].send_data_for_led_addressing(True)
            else:
                # time.sleep(.25)
                self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].send_data_for_led_addressing(True)
        return 

    def on_manually_control_led_range_slider_event(self):
        """Handles an event in which the user has altered the value of a led range slider in one of the LED range sliders displayed on the GUI inside of the Subsystem Frames. If there is a connection to a server,
        this event will update the state of the LED slider range specified by the user in the physical LED Subsystem."""
        if not self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].manual_status:
            return
        if self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].client_conn:
            if self.values[f'-CAMERA_{self.event_camera}_SLIDER_LEFT_TO_RIGHT-']:
                on_led_range = (0, round(self.values[f'-CAMERA_{self.event_camera}_LEDSLIDER-']))
            elif self.values[f'-CAMERA_{self.event_camera}_SLIDER_RIGHT_TO_LEFT-']:
                on_led_range = (round(self.values[f'-CAMERA_{self.event_camera}_LEDSLIDER-']), self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].number_of_leds)
            else:
                on_led_range = False
            if on_led_range == (0, 0) or on_led_range == (self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].number_of_leds, self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].number_of_leds):
                on_led_range = False
            self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].system_led_data.manual_led_data.set_slider_led_range(on_led_range)
            if not self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].auto_status:
                self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].send_data_for_led_addressing(True)
            else:
                # time.sleep(.25)
                self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].send_data_for_led_addressing(True)
        return
    
    def on_manually_control_led_brightness_slider_event(self):
        """Handles an event in which the user has altered the value of a led brightness slider in one of the LED brightness sliders displayed on the GUI inside of the Subsystem Frames. 
        If there is a connection to a server, this event will update the state of the LED slider brightness specified by the user in the physical LED Subsystem."""
        if not self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].manual_status:
            return
        if self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].client_conn:
            brightness = round(self.values[f'-CAMERA_{self.event_camera}_BRIGHTNESSSLIDER-'] * .01, 2)
            self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].system_led_data.manual_led_data.brightness = brightness
            if not self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].auto_status:
                self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].send_data_for_led_addressing(True)
            else:
                # time.sleep(.25)
                self.lit_subsystem_dict[f'CAMERA_{self.event_camera}'].send_data_for_led_addressing(True)

            
    def disable_all_manual_options_of_subsystem(self):
        """Disable all manual options of the subsystem panel where this event originated."""
        self.disable_all_led_range_checkboxs()
        self.disable_adjust_leds_left_to_right()
        self.disable_adjust_brightness_of_leds()
        self.disable_left_to_right_checkbox()
        self.disable_right_to_left_checkbox()
        self.disable_turn_all_leds_on_checkbox()
        return

    def enable_all_manual_options_of_subsystem(self):
        """Enables all manual options of the subsystem panel where this event originated."""
        self.enable_all_led_range_checkboxs()
        self.enable_adjust_leds_left_to_right()
        self.enable_adjust_brightness_of_leds()
        self.enable_left_to_right_checkbox()
        self.enable_right_to_left_checkbox()
        self.enable_turn_all_leds_on_checkbox()
        return
    
    def enable_turn_all_leds_on_checkbox(self):
        self.window[f'-CAMERA_{self.event_camera}_TURNONALLLEDs-'].update(disabled=False)
        return
    
    def enable_all_led_range_checkboxs(self):
        """Iterates over all of the LED Range checkboxes in a panel and enables them for user interaction."""
        for led_tuple in self.led_tuples_dict_of_list[f'CAMERA_{self.event_camera}']:
            self.window[f'-CAMERA_{self.event_camera}_LEDRANGE_{led_tuple[0]}_{led_tuple[1]}-'].update(disabled=False)
        return
    
    def enable_adjust_leds_left_to_right(self):
        """Enables the led slider of the current panel where this event orginiated."""
        self.window[f'-CAMERA_{self.event_camera}_LEDSLIDER-'].update(disabled=False)
        return

    def enable_adjust_brightness_of_leds(self):
        """Enables the led brightness slider of the current panel where this event orginiated."""
        self.window[f'-CAMERA_{self.event_camera}_BRIGHTNESSSLIDER-'].update(disabled=False)
        return
    
    def enable_right_to_left_checkbox(self):
        """Enables the checkbox for using the led slider in left to right mode. This change is applied to the current panel where this event orginiated."""
        self.window[f'-CAMERA_{self.event_camera}_SLIDER_LEFT_TO_RIGHT-'].update(disabled=False)
        return
    
    def enable_left_to_right_checkbox(self):
        """Enables the checkbox for using the led slider in right to left mode. This change is applied to the current panel where this event orginiated."""
        self.window[f'-CAMERA_{self.event_camera}_SLIDER_RIGHT_TO_LEFT-'].update(disabled=False)
        return
    
    def disable_all_led_range_checkboxs(self):
        """Iterates over all of the LED Range checkboxes in a panel and enables them for user interaction."""
        for led_range in self.led_tuples_dict_of_list[f'CAMERA_{self.event_camera}']:
            self.window[f'-CAMERA_{self.event_camera}_LEDRANGE_{led_range[0]}_{led_range[1]}-'].update(disabled=True)
        return
    
    def disable_adjust_leds_left_to_right(self):
        """Disables the led slider of the current panel where this event orginiated."""
        self.window[f'-CAMERA_{self.event_camera}_LEDSLIDER-'].update(disabled=True)
        return

    def disable_adjust_brightness_of_leds(self):
        """Disables the led brightness slider of the current panel where this event orginiated."""
        self.window[f'-CAMERA_{self.event_camera}_BRIGHTNESSSLIDER-'].update(disabled=True)
        return
    
    def disable_right_to_left_checkbox(self):
        """Enables the checkbox for using the led slider in right to left mode. This change is applied to the current panel where this event orginiated."""
        self.window[f'-CAMERA_{self.event_camera}_SLIDER_RIGHT_TO_LEFT-'].update(disabled=True)
        return
    
    def disable_left_to_right_checkbox(self):
        """Enables the checkbox for using the led slider in left to right mode. This change is applied to the current panel where this event orginiated."""
        self.window[f'-CAMERA_{self.event_camera}_SLIDER_LEFT_TO_RIGHT-'].update(disabled=True)
        return
    
    def disable_turn_all_leds_on_checkbox(self):
        self.window[f'-CAMERA_{self.event_camera}_TURNONALLLEDs-'].update(disabled=True)
        return
    
    def turn_right_to_left_status_to_false(self):
        """Sets the status of the checkbox for using the led slider in right to left mode to False. This change is applied to the current panel where this event orginiated."""
        self.window[f'-CAMERA_{self.event_camera}_SLIDER_RIGHT_TO_LEFT-'].update(False)
        self.values[f'-CAMERA_{self.event_camera}_SLIDER_RIGHT_TO_LEFT-'] = False
        return

    def turn_left_to_right_status_to_false(self):
        """Sets the status of the checkbox for using the led slider in left to right mode to False. This change is applied to the current panel where this event orginiated."""
        self.window[f'-CAMERA_{self.event_camera}_SLIDER_LEFT_TO_RIGHT-'].update(False)
        self.values[f'-CAMERA_{self.event_camera}_SLIDER_LEFT_TO_RIGHT-'] = False
        return

    def get_led_range_from_event(self)->tuple:
        """Returns the tuple of ints from a checkbox event in the Adjust LED range subframe. Used to parse the str displayed to the user and only return the int values."""
        return tuple(int(x) for x in self.event.replace('-','').split('_')[3:])

    def get_value_of_element_from_event(self)->bool:
        """Returns the value of the element where an event spawns."""
        return self.values[self.event]
    
    
    def start_event_loop(self):
        """Creates a loop that runs endlessly while the GUI is running, handles all events the occur in the GUI."""
        while True:             
            self.event, self.values = self.window.Read()
            if self.event is None: #MAYBE, JUST MAYBE WE LISTEN HERE FOR SERVER STATUS/SEEMS UNNECCESARY I think``
                break
            self.set_camera_of_event()
            if 'SHOWFEED' in self.event:
                self.on_show_camera_feed_event()
            elif 'MANUALSTATUS' in self.event:
                self.on_manual_control_event()
            elif 'AUTONOMOUSMODE' in self.event:
                self.on_autonomous_mode_event()
            elif '_HANDGESTUREDETECTION' in self.event:
                self.on_hand_gesture_detection()
            elif '_TURNONALLLEDs' in self.event:
                self.on_turn_on_all_leds()
            elif '_LEDRANGE_' in self.event:
                self.on_manually_control_led_range_event()
            elif '_SLIDER_LEFT_TO_RIGHT' in self.event:
                self.turn_right_to_left_status_to_false()
                self.on_manually_control_led_range_slider_event()
            elif '_SLIDER_RIGHT_TO_LEFT' in self.event:
                self.turn_left_to_right_status_to_false()
                self.on_manually_control_led_range_slider_event()
            elif '_LEDSLIDER-' in self.event and 'Release' not in self.event:
                self.on_manually_control_led_range_slider_event()
            elif '_LEDSLIDER-' in self.event and 'Release' in self.event:
                # time.sleep(0.5)
                self.on_manually_control_led_range_slider_event()
            elif '_BRIGHTNESSSLIDER' in self.event and 'Release' not in self.event:
                self.on_manually_control_led_brightness_slider_event()
            elif '_BRIGHTNESSSLIDER' in self.event and 'Release' in self.event:
                # time.sleep(0.5)
                self.on_manually_control_led_brightness_slider_event()
            elif 'UPDATE_' in self.event and '_FRAME' in self.event:
                img_bytes = self.get_value_of_element_from_event()
                self.window[f'-CAMERA_{self.event_camera}_FEED-'].update(data=img_bytes)
            elif '_HANDGESTURETURNONALLLEDS' in self.event:
                time.sleep(.5)
                self.window[f'-CAMERA_{self.event_camera}_TURNONALLLEDs-'].update(self.values[f'-CAMERA_{self.event_camera}_HANDGESTURETURNONALLLEDS-'])
                self.on_turn_on_all_leds()
            elif '_HANDGESTUREINCREASEBRIGHTNESS' in self.event:
                time.sleep(.1)
                self.window[f'-CAMERA_{self.event_camera}_BRIGHTNESSSLIDER-'].update(self.values[f'-CAMERA_{self.event_camera}_BRIGHTNESSSLIDER-'] + 2)
                self.on_manually_control_led_brightness_slider_event()    
            elif '_HANDGESTUREDECREASEBRIGHTNESS' in self.event:        
                time.sleep(.1)
                if self.values[f'-CAMERA_{self.event_camera}_BRIGHTNESSSLIDER-'] < 2:
                    self.values[f'-CAMERA_{self.event_camera}_BRIGHTNESSSLIDER-'] = 0
                    time.sleep(.5)
                else:
                    self.window[f'-CAMERA_{self.event_camera}_BRIGHTNESSSLIDER-'].update(self.values[f'-CAMERA_{self.event_camera}_BRIGHTNESSSLIDER-'] - 2)
                self.on_manually_control_led_brightness_slider_event()    
            elif '_HANDGESTUREINCREASELEDRANGE' in self.event:
                time.sleep(.1)
                self.window[f'-CAMERA_{self.event_camera}_LEDSLIDER-'].update(self.values[f'-CAMERA_{self.event_camera}_LEDSLIDER-'] + 2)
                self.on_manually_control_led_range_slider_event()
            elif '_HANDGESTUREDECREASELEDRANGE' in self.event:
                time.sleep(.1)
                if self.values[f'-CAMERA_{self.event_camera}_LEDSLIDER-'] < 2:
                    time.sleep(.5)
                    self.values[f'-CAMERA_{self.event_camera}_LEDSLIDER-'] = 0
                else:
                    self.window[f'-CAMERA_{self.event_camera}_LEDSLIDER-'].update(self.values[f'-CAMERA_{self.event_camera}_LEDSLIDER-'] - 2)
                self.on_manually_control_led_range_slider_event()
            elif '_HANDGESTURELEDRANGELEFTRIGHT' in self.event:
                time.sleep(.1)
                self.window[f'-CAMERA_{self.event_camera}_SLIDER_LEFT_TO_RIGHT-'].update(True)
                self.turn_right_to_left_status_to_false()
                self.on_manually_control_led_range_slider_event()
            elif '_HANDGESTURELEDRANGERIGHTLEFT' in self.event:
                time.sleep(.1)
                self.window[f'-CAMERA_{self.event_camera}_SLIDER_RIGHT_TO_LEFT-'].update(True)
                self.turn_left_to_right_status_to_false()
                self.on_manually_control_led_range_slider_event()
        return
    