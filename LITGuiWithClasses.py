#I need to add a detailed description of this file for sharing with the world aka GitHub
import PySimpleGUI as sg
import typing
from LITGuiEventHandler import LITGuiEventHandler
import ObjectDetectionModel
from ObjectDetectionModel import ObjectDetectionModel
import threading
import socket
import pickle
from LITSubsystemInterface import LITSubsystemData
import math
import os
import numpy as np
# used to prevent popup froms occur while debugging and poential errors that are inevitable but caught with try and excepts from also creating annoying popups
sg.set_options(suppress_raise_key_errors=True, suppress_error_popups=True, suppress_key_guessing=True)




class LITGUI(LITGuiEventHandler):
    """Abstract GUI Class used to create a GUI that displays live camera feed for N number of cameras, with each camera camera in the GUI having its own section to turn off and on
    Object Detection, if the user provides a ObjectDetectionModel for each Subsystem passed. Allows for the manual control of LED subsystems associated with each Subsystem represented by their 
    unique cameras. Can be scalled to as many Cameras and Subsystems the user would like to run.
    """


    def __init__(self, lit_subsystem_data: typing.Union[LITSubsystemData, list[LITSubsystemData]], background_images_dir: str):
        """Creates a GUI displaying Camera Feeds for each LITSubsystemData instance passed.
        
        Parameters:
        - lit_subsystem_data (typing.Union[LITSubsystemData, list[LITSubsystemData]]): Will create a seperate section in the GUI for each subsystem passed, whether in a list of Length N, or 
        if a single instance of LITSubsystemData is passed."""
        LITGuiEventHandler.__init__(self, background_images_dir)
        self.led_tuples_dict_of_list: dict[str, list[tuple[int, int]]] = {}
        self.object_detection_model_dict: dict[str, typing.Union[ObjectDetectionModel, None]] = {}
        self.lit_subsystem_dict: dict[str, LITSubsystemData] = {}
        if isinstance(lit_subsystem_data, LITSubsystemData):
            final_layout = self.create_gui_from_camera_instance(lit_subsystem_data)
            self.window = sg.Window('Test', final_layout, finalize=True, resizable=False)
            self.bind_all_slider_release_events(lit_subsystem_data.camera_idx)
        elif isinstance(lit_subsystem_data, list):
            final_layout = self.create_gui_from_cameras_list(lit_subsystem_data)
            self.window = sg.Window('Test', final_layout, finalize=True, resizable=False)
            self.bind_all_slider_release_events([lit_subsystem.camera_idx for lit_subsystem in lit_subsystem_data])
        self.set_lit_subsystems_windows(lit_subsystem_data)
        return

    def bind_all_slider_release_events(self, camera_idx: typing.Union[int, list[int]]):
        """Binds a button release event to the current camera panel's brightness and led sliders. This enables control of slider release events, such as storing the value of the slider once user has finished 
        using it, as if it is slid to fast the main loop can not keep up.
        
        Parameters:
        - camera_idx (typing.Union[int, list[int]]): The camera ID used to address the current panel elements. Each panel has its own elements where the camera ID is added to make them unique."""

        if isinstance(camera_idx, int):
            self.window[f'-CAMERA_{camera_idx}_LEDSLIDER-'].bind('<ButtonRelease-1>', ' Release')
            self.window[f'-CAMERA_{camera_idx}_BRIGHTNESSSLIDER-'].bind('<ButtonRelease-1>', ' Release')
        elif isinstance(camera_idx, list):
            for idx in camera_idx:
                self.window[f'-CAMERA_{idx}_LEDSLIDER-'].bind('<ButtonRelease-1>', ' Release')
                self.window[f'-CAMERA_{idx}_BRIGHTNESSSLIDER-'].bind('<ButtonRelease-1>', ' Release')
        return
            
    def set_lit_subsystems_windows(self, lit_subsystem_data: typing.Union[LITSubsystemData, list[LITSubsystemData], None, list[None]]):
        """Sets the window where each object detection model will pass data to, which will be the window created by an instance of this class.
        
        Parameters:
        - lit_subsystem_data (typing.Union[LITSubsystemData, list[LITSubsystemData], None, list[None]]): An instance of the LITSubsystemData class, or a list containing either all LITSubsystemData 
        instances, or some LITSubsystemData instances and some Nonetype instances."""

        if isinstance(lit_subsystem_data, LITSubsystemData):
            if lit_subsystem_data.object_detection_model:
                lit_subsystem_data.object_detection_model.set_window(self.window)
        elif isinstance(lit_subsystem_data, list):
            for subsystem in lit_subsystem_data:
                if isinstance(subsystem.object_detection_model, ObjectDetectionModel):
                    subsystem.object_detection_model.set_window(self.window)
        return
    
    def create_led_tuple_range_list(self)->list[tuple[int, int]]:
        """Returns a list of tuples containing the start and stopping point of LED ranges based on the number of LEDs of the subsystem specified divided by the number of sections the user would 
        like the subsystem divided into."""

        led_tuples_list = []
        leds_ranges = round(self.number_of_leds/self.num_of_sections)
        i = 0
        while i < self.number_of_leds:
            led_tuples_list.append((i, i+leds_ranges))
            i += leds_ranges
        return led_tuples_list
    
    def add_object_detection_model_to_gui(self, object_detection_model: typing.Union[ObjectDetectionModel, None]):
        """Sets the image window where video feed will be passed from the object detection model to the GUI window. Also adds the key value pair of the camera_idx and the object model instance to the 
        object detection model dictionary
        
        Parameters:
        - object_detection_model (typing.Union[ObjectDetectionModel, None]): an instance of the ObjectDetectionModel, or a NoneType instance.
        """
        if isinstance(object_detection_model, ObjectDetectionModel):
            object_detection_model.set_image_window(f'-CAMERA_{self.camera_idx}_FEED-')
        self.object_detection_model_dict[f'CAMERA_{self.camera_idx}'] = object_detection_model
        return

    def create_camera_frame(self, lit_subsystem_data: LITSubsystemData):
        """Creates a frame for a LITSubsystemData instance passed. This Frame contains all of the User Interface relevant to the provided LITSubsystem.
        
        Parameters:
        - lit_subsystem_data (LITSubsystemData): An instance of the LITSubsystemData class."""

        self.camera_idx = lit_subsystem_data.camera_idx
        self.number_of_leds = lit_subsystem_data.number_of_leds
        self.num_of_sections = lit_subsystem_data.number_of_sections
        self.gui_image_preview_width = lit_subsystem_data.image_preview_width
        self.gui_image_preview_height = lit_subsystem_data.image_preview_height
        self.lit_subsystem_dict[f'CAMERA_{self.camera_idx}'] = lit_subsystem_data
        self.add_object_detection_model_to_gui(lit_subsystem_data.object_detection_model)
        led_tuples_list = self.create_led_tuple_range_list()
        self.led_tuples_dict_of_list[f"CAMERA_{self.camera_idx}"] =led_tuples_list
        leds_range_option_with_frame = self.create_control_led_range_frame()
        slider_led_range_option_with_frame = self.create_led_slider_range_frame()
        slider_brightness_range_option_with_frame = self.create_brightness_slider_range_frame()
        control_buttons_row = self.create_enable_controls_row()
        image_preview_section = self.create_image_preview_section()
        layout = [control_buttons_row, [leds_range_option_with_frame], [slider_led_range_option_with_frame], [slider_brightness_range_option_with_frame]]
        controller_options_section_layout = self.create_controller_options_section_wrapped_in_frame(layout)

        final_layout = self.create_final_subsystem_section_layout_wrapped_in_frame(image_preview_section, controller_options_section_layout)
        return final_layout

    def create_image_preview_section(self):
        """Creates the image element for the current Subsystem Frame being created. This is video feed will be displayed."""
        if self.camera_idx == 0:
            camera_preview = [sg.Image(filename=r'BackgroundImages\gon.png',
                                        key=f'-CAMERA_{self.camera_idx}_FEED-', size=(self.gui_image_preview_width, self.gui_image_preview_height))] 
        else:
            camera_preview = [sg.Image(filename=r'BackgroundImages\killua.png', 
                                       key=f'-CAMERA_{self.camera_idx}_FEED-', size=(self.gui_image_preview_width, self.gui_image_preview_height))]

        return camera_preview

    def create_enable_controls_row(self)->list[sg.Checkbox]:
        """Creates the main controls row, which contains the checkboxes for enabling manual control of the LED subsystem, Turning all LEDs on, Autonomous Mode, and showing the camera feed."""
        control_buttons_row = [sg.Checkbox(f"Manually Control LIT Subsystem {self.camera_idx}", size=(23,1), key=f'-CAMERA_{self.camera_idx}_MANUALSTATUS-', enable_events=True),
                               sg.Checkbox(f"Hand Gesture Detection", size=(18,1), key=f'-CAMERA_{self.camera_idx}_HANDGESTUREDETECTION-', enable_events=True, disabled=True),
                                sg.Checkbox(f"Autonomous Mode", size=(13,1), key=f'-CAMERA_{self.camera_idx}_AUTONOMOUSMODE-', enable_events=True), 
                                sg.Checkbox(f"Show Camera Feed", size=(15,1), key=f'-CAMERA_{self.camera_idx}_SHOWFEED-', enable_events=True, disabled=True)]
        
        return control_buttons_row

    def create_control_led_range_frame(self)->sg.Frame:
        """Creates the Frame containing checkboxes for manually controlling sections of the LED Subsystem with checkboxes which each refer to a specific section."""
        leds_range_option_in_frame = []
        for led_range in self.led_tuples_dict_of_list[f'CAMERA_{self.camera_idx}']:
            
            leds_range_option_in_frame.append(sg.Checkbox(f"({led_range[0]}, {led_range[1]})",  size=((len(str(led_range[0]))+1+len(str(led_range[1]))),1), \
                                                  key=f'-CAMERA_{self.camera_idx}_LEDRANGE_{led_range[0]}_{led_range[1]}-', enable_events=True, disabled=True))
            
        total_text_len = sum([len(str(led_range[0]))+1+len(str(led_range[1])) for led_range in self.led_tuples_dict_of_list[f'CAMERA_{self.camera_idx}']])
        number_of_checkboxes_per_row = math.ceil(self.gui_image_preview_width / total_text_len) 
        leds_range_option_in_frame = list(split(leds_range_option_in_frame, number_of_checkboxes_per_row))
        leds_range_option_with_frame = sg.Frame('Manually Control LED Ranges', leds_range_option_in_frame, expand_x=True)

        return leds_range_option_with_frame

    def create_led_slider_range_frame(self)->sg.Frame:
        """Creates the Frame containing checkboxes and a slider for manually controlling consecutive leds in the LED Subsystem."""
        slider_led_range_option_inside_frame = [[sg.Checkbox(f'Adjust LEDs Left To Right', size=(23,1), key=f'-CAMERA_{self.camera_idx}_SLIDER_LEFT_TO_RIGHT-', enable_events=True, default=True, disabled=True),
                                                 sg.Checkbox(f'Adjust LEDs Right To Left', size=(23,1), key=f'-CAMERA_{self.camera_idx}_SLIDER_RIGHT_TO_LEFT-', enable_events=True, disabled=True),
                                                 sg.Checkbox(f"Turn On All LEDs", size=(15,1), key=f'-CAMERA_{self.camera_idx}_TURNONALLLEDs-', enable_events=True, disabled=True)],
                                                [sg.Slider((0,self.number_of_leds), 0,1, orientation='h', size=(20,15), key=f'-CAMERA_{self.camera_idx}_LEDSLIDER-',\
                                                            enable_events=True, expand_x=True, disabled=True)]]
        slider_led_range_option_with_frame = sg.Frame('Adjust LEDs Consecutively', slider_led_range_option_inside_frame, expand_x=True)
        
        return slider_led_range_option_with_frame

    def create_brightness_slider_range_frame(self)->sg.Frame:
        """Creates the Frame containing the brightness slider used to set the brightness of manual controled LEDs."""
        slider_brightness_range_option_inside_frame = [[sg.Slider((0, 100), 0, 1, orientation='h', size=(20,15), key=f'-CAMERA_{self.camera_idx}_BRIGHTNESSSLIDER-', \
                                                                   enable_events=True, expand_x=True, disabled=True)]]
        slider_brightness_range_option_with_frame = sg.Frame('Adjust Brightness of LEDs (in Percentages)', slider_brightness_range_option_inside_frame, expand_x=True)
        
        return slider_brightness_range_option_with_frame

    def create_controller_options_section_wrapped_in_frame(self, layout_list: list)->sg.Frame:
        """Creates a Frame around the Current Subsystem Control Settings being created in the GUI. Used to seperate Subsystem Control Settings from the Camera feed."""
        return sg.Frame(f'Camera {self.camera_idx} Subsystem Controller', layout_list, expand_x=True)

    def create_final_subsystem_section_layout_wrapped_in_frame(self, image_preview_section, controller_options_section_layout)->sg.Frame:
        """Creates a Frame around the Current Subsystem Panel being created. Used to seperate Subsystems from one another in the GUI."""
        final_layout = [image_preview_section, [controller_options_section_layout]]
        return sg.Frame(f'Camera {self.camera_idx} Subsystem', final_layout, expand_y=True)

    def create_gui_from_cameras_list(self, lit_subsystem_data: list[LITSubsystemData])->list[list[sg.Frame]]:
        """Creates all of the Subsystem Frames which are displayed in the Gui. This is passed to the sg.Window class to create the final GUI."""
        return [[self.create_camera_frame(subsystem_data) for subsystem_data in lit_subsystem_data]]

    def create_gui_from_camera_instance(self, lit_subsystem_data: LITSubsystemData)->list[list[sg.Frame]]:
        """Creates a LITSubsystem Frame which is displayed in the GUI. Called when user provides only one LITSubsystem data instance to the constructor."""
        return [[self.create_camera_frame(lit_subsystem_data)]]




def split(list_a, chunk_size):
  for i in range(0, len(list_a), chunk_size):
    yield list_a[i:i + chunk_size]



