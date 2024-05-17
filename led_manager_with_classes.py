import time
import board
import neopixel
import pickle
import typing


class LEDPanels:
    """Used to interface with an LED system. Allows for cascading of NeoPixel Panels of the same size, where sections of the LEDs can be directly altered with APIs.
    
    Attributes:
    
    - auto_mode_status (bool): Enables/Disables the ability to update the LEDs without user interference using the ObjectDetectionModel Module.
    - manual_mode_status (bool): Enables/Disables the ability to update the LEDs with user interference such as calling led update methods, or using the GUI in LUIGui Module.
    - manual_brightness (float): Sets the class brightness for any LED that is being manually controlled.
    - manual_led_ranges (list[tuple]): The current list of LED ranges the user is manually turning on in the LITGui Module.
    - manual_led_with_sliders (tuple): The current range of LEDs the user is manually turning on with the LED slider in the LITGui Module."""

    auto_mode_status: bool = False
    manual_mode_status: bool = False
    manual_brightness: float = 0
    manual_led_ranges: list[tuple] = [(0, 0)]
    manual_led_with_sliders: tuple = (0, 0)

    def __init__(self, board_pin: board, num_of_leds: int = 800, brightness: float = 1):
        """Using a board pin, this initializes the current class and an instance of the NeoPixel class."""
        self.board_pixels = neopixel.NeoPixel(board_pin, num_of_leds, brightness=brightness)
        return


    def auto_turn_off_led_ranges(self, turn_off_tuple_list: list[tuple], manual_event = False):
        """Turn off all ranges in the provided turn_off_tuple_list, this will ignore leds that are currently set to be turned on manually if the manual mode is enabled.
        This will update the LEDs in the same column amongst all of the panels.
        
        Parameters:
        - turn_off_tuple_list (list[tuple]): A list of tuples containing the start and stop values of the range of LEDs to turn off."""
        if isinstance(turn_off_tuple_list, tuple):
            turn_off_tuple_list = [turn_off_tuple_list]
        
        for turn_off_range in turn_off_tuple_list:
            if self.manual_mode_status and not manual_event:
                print(f'auto turn off range {turn_off_range}')
                if self.range_is_in_manual_mode_section(turn_off_range):
                    continue
            

            first_led = turn_off_range[0] 
            last_led = turn_off_range[-1] 

            first_led_mid_panel = 512 - last_led 
            last_led_mid_panel = 512 - first_led

            first_led_last_panel = first_led + 511
            last_led_last_panel = last_led + 512

            self.board_pixels[first_led: last_led] = [(0,0,0)] * (last_led-first_led)

            self.board_pixels[first_led_mid_panel: last_led_mid_panel] = [(0,0,0)] * (last_led_mid_panel-first_led_mid_panel)

            self.board_pixels[first_led_last_panel: last_led_last_panel] = [(0,0,0)] * (last_led_last_panel-first_led_last_panel)
        return


    def auto_update_leds(self, objs_detect_stats_list_of_dicts: list[dict]):
        """Used as part of the Object Detection Model Subsystem, where this method will update the status of any LED that is not apart of the manually selected LEDs if manual status is enabled, using the data from the Object Detection Model.
        
        Parameters:
        - objs_detect_stats_list_of_dicts (list[dict]): The list of dictonaries containing start and stop ranges of LEDs to turn on at a specified brightness in the respective dictionary."""

        for led_dict in objs_detect_stats_list_of_dicts:
            if not led_dict:
                continue
            if self.manual_mode_status:
                if self.range_is_in_manual_mode_section(led_dict['led_tuple']):
                    continue
            self.update_current_auto_detect_led_tuple_ranges(led_dict)
        return

    def turn_on_manual_range(self, manual_led_tuple: tuple[int, int]):
        """Used to manually specify LED Ranges to turn on, called from GUI events, or can be called as a standalone method.
        
        Parameters:
        - manual_led_tuple (tuple[int, int]): A range of LEDs to turn on at the brightness stored in the manual brightness attribute."""
        if not manual_led_tuple:
            return
        leds_tuple_mid_panel = (512-manual_led_tuple[1], 512-manual_led_tuple[0])
        leds_tuple_top_panel = (manual_led_tuple[0]+512, manual_led_tuple[1]+512)
        
        self.board_pixels[manual_led_tuple[0]:manual_led_tuple[1]] = [(0,0,round(255*self.manual_brightness))] * (manual_led_tuple[1]-manual_led_tuple[0])

        self.board_pixels[leds_tuple_mid_panel[0]:leds_tuple_mid_panel[1]] = [(0,0,round(255*self.manual_brightness))] * (leds_tuple_mid_panel[1]-leds_tuple_mid_panel[0])

        self.board_pixels[leds_tuple_top_panel[0]:leds_tuple_top_panel[1]] = [(0,0,round(255*self.manual_brightness))] * (leds_tuple_top_panel[1]-leds_tuple_top_panel[0])
        return
    
    def update_current_auto_detect_led_tuple_ranges(self, led_dict: dict[float, tuple[int, int]]):
        """Updates the current LED range provided in the dict with the brightness provided. This will update all leds in the specified column (range).
        
        Parameters:
        
        - led_dict (dict[float, tuple[int, int]]): A dictonary containing two sets of key-value pairs, where the brightness to set the current LED range to is stored in the key 'brightness' as a float (0.00-1.00), 
        and the led tuple used to speicfy the range is stored in 'led_tuple'."""

        brightness = float(led_dict['brightness'])
        leds_tuple = led_dict['led_tuple']
        leds_tuple_mid_panel = (512-leds_tuple[1], 512-leds_tuple[0])
        leds_tuple_top_panel = (leds_tuple[0]+512, leds_tuple[1]+512)
        
        self.board_pixels[leds_tuple[0]:leds_tuple[1]] = [(0,0,round(255*brightness))] * (leds_tuple[1]-leds_tuple[0])

        self.board_pixels[leds_tuple_mid_panel[0]:leds_tuple_mid_panel[1]] = [(0,0,round(255*brightness))] * (leds_tuple_mid_panel[1]-leds_tuple_mid_panel[0])

        self.board_pixels[leds_tuple_top_panel[0]:leds_tuple_top_panel[1]] = [(0,0,round(255*brightness))] * (leds_tuple_top_panel[1]-leds_tuple_top_panel[0])
        return
    
    def manual_brightness_adjust_of_manual_ranges(self):
        """Used when the brightness is manually adjusted, this method iterates over all ranges over currently manually controlled LEDs and updates their brightnesses."""
        if self.manual_led_ranges:
            for led_tuple in self.manual_led_ranges:
                self.turn_on_manual_range(led_tuple)

        if self.manual_led_with_sliders:
            self.turn_on_manual_range(self.manual_led_with_sliders)
        return


    def update_leds_from_data_packets(self, data: list):
        """Used to update LEDs from a server connection, first the data is assumed to be pickled and therefore must be unpickled. This handles packets received from the ObjectDetectionModel or the LITGui Modules.
        
        Parameters:
        - data: UPDATE"""

        try:
            detect_obj = pickle.loads(data)
        except:
            detect_obj = data
        try:
            if detect_obj[0] == 'AUTO_LED_DATA':
                if detect_obj[1]:
                    self.auto_update_leds(detect_obj[1])
                if detect_obj[2]:
                    self.auto_turn_off_led_ranges(detect_obj[2])
            elif detect_obj[0] == 'UPDATE_AUTO_STATUS':
                self.update_auto_mode_status(detect_obj[1])
            elif detect_obj[0] == 'MANUAL':
                self.handle_manual_mode_event(detect_obj)
        except:
            pass

    def range_is_in_manual_mode_section(self, turn_off_range: tuple[int, int])->bool:
        """Check if a range to be updated automatically is currently being controlled by one of the manually settings.
        
        Parameters:
        - turn_off_range (tuple[int, int]): The range of leds to change the status of represented as a tuple of the start and stop points."""

        if self.manual_led_ranges and self.manual_led_with_sliders:
            if any(is_overlap(turn_off_range, led_range) for led_range in self.manual_led_ranges) or is_overlap(turn_off_range, self.manual_led_with_sliders):
                return True
            return False
        elif self.manual_led_ranges:
            if any(is_overlap(turn_off_range, led_range) for led_range in self.manual_led_ranges):
                return True
            return False
        elif self.manual_led_with_sliders:
            if is_overlap(turn_off_range, self.manual_led_with_sliders):
                return True
            return False
        return False
    
    def handle_manual_mode_event(self, detect_obj: list[str, str, typing.Union[tuple, float]]):
        """Handles an event in which the user would like to manually update the LEDs from either the LITGui Module, or using this method directly.
        
        Parameters:
        - detect_obj: (list[str, str, typing.Union[tuple, float]]): The information related to the manual update operation. Example input:  ['MANUAL', 'LED_RANGE_APPEND', (0,31)]"""
        if detect_obj[1] == 'MANUAL_STAUS':
            self.manual_mode_status = detect_obj[2]
            self.handle_update_of_manual_mode_or_auto_mode_status()
        elif detect_obj[1] == 'LED_RANGE_APPEND':
            self.manual_led_ranges.append(detect_obj[2])
            self.turn_on_manual_range(detect_obj[2])
        elif detect_obj[1] == 'LED_RANGE_REMOVE':
            self.manual_led_ranges.remove(detect_obj[2])
            #this may need a turn off manual range function that turns off the LEDS immedadlity 
            if not self.auto_mode_status:
                self.auto_turn_off_led_ranges([detect_obj[2]])
        elif detect_obj[1] == 'BRIGHTNESS':
            self.manual_brightness = detect_obj[2]
            self.manual_brightness_adjust_of_manual_ranges()
        elif detect_obj[1] == 'LED_SLIDER_RANGE':
            self.manual_led_with_sliders = detect_obj[2]
            if self.manual_led_with_sliders:
                self.turn_on_manual_range(detect_obj[2])
            if not self.auto_mode_status:
                if self.manual_led_with_sliders:
                    self.manual_led_ranges.append(self.manual_led_with_sliders)
                turn_off_ranges = find_missing_numbers_as_ranges_tuples(self.manual_led_ranges)
                self.auto_turn_off_led_ranges(turn_off_ranges, True)
                if self.manual_led_with_sliders:
                    self.manual_led_ranges.remove(self.manual_led_with_sliders)
    def update_auto_mode_status(self, auto_mode_status: bool):
        """Update the state of the auto mode status attribute."""
        self.auto_mode_status = auto_mode_status
        return

    def handle_update_of_manual_mode_or_auto_mode_status(self):
        """If the LED panel has nothing provided control of the lights anymore, turn them all off."""
        if not self.manual_mode_status and not self.auto_mode_status:
            self.auto_turn_off_led_ranges([(0, 255)], True)
        elif not self.auto_mode_status:
            self.turn_on_manual_range(self.manual_led_with_sliders)
            for led_range in self.manual_led_ranges:
                self.turn_on_manual_range(led_range)
                if self.manual_led_with_sliders:
                    self.manual_led_ranges.append(self.manual_led_with_sliders)
                turn_off_ranges = find_missing_numbers_as_ranges_tuples(self.manual_led_ranges)
                self.auto_turn_off_led_ranges(turn_off_ranges, True)
                if self.manual_led_with_sliders:
                    self.manual_led_ranges.remove(self.manual_led_with_sliders)
        return

def find_missing_numbers_as_ranges_tuples(ranges) -> list[tuple]:
    # Initialize a set with all numbers from 0 to 256
    all_numbers = set(range(257))
    
    # Remove the numbers present in the given ranges
    for start, end in ranges:
        all_numbers -= set(range(start, end + 1))
    
    # Convert the set to a sorted list
    missing_numbers_sorted = sorted(list(all_numbers))
    
    # Group the consecutive numbers into ranges
    missing_ranges = []
    if missing_numbers_sorted:
        # Initialize the first range with the first missing number
        range_start = missing_numbers_sorted[0]
        range_end = missing_numbers_sorted[0]
        
        for number in missing_numbers_sorted[1:]:
            if number == range_end + 1:
                # Extend the current range
                range_end = number
            else:
                # Finish the current range and start a new one
                missing_ranges.append((range_start, range_end))
                range_start = number
                range_end = number
        
        # Add the last range
        missing_ranges.append((range_start, range_end))
    
    return missing_ranges
def is_overlap(range1, range2):
    """Check if range1 overlaps with range2."""
    if (range1[0] < range2[1]) and (range1[1] > range2[0]):
        return True
    return False