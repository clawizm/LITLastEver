import typing
import itertools
import math
class ManualLEDData:
    """Stores all user entered manual LED Data, where all led ranges stored in this class share single brightness"""
    def __init__(self, brightness: float = 0.00):
        """Creates a container storing relevant user defined LED data."""

        self.brightness = brightness
        self.manual_led_tuple_list: list[tuple[int, int]] = []
        self.slider_led_tuple: tuple[int, int] = None
        return
    
    def add_led_range(self, led_range: tuple[int, int]):
        """Add an LED range to the list of tuples stored in this container.
        
        Parameters:
        - led_range (tuple[int, int]): The led_range the user would like to add to this container, in the form of a tuple."""

        self.manual_led_tuple_list.append(led_range)
        return
        
    def remove_led_range(self, led_range: tuple[int, int]):
        """Remove an LED range to the list of tuples stored in this container.
        
        Parameters:
        - led_range (tuple[int, int]): The led_range the user would like to remove from this container, in the form of a tuple."""

        self.manual_led_tuple_list.remove(led_range)
        return
    
    def set_slider_led_range(self, led_range: tuple[int, int]):
        """Set the value of the LED range provided in the LED slider.
        
        Parameters:
        - led_range (tuple[int, int]): The led_range the user would like to store as the slider range in this container, in the form of a tuple."""

        self.slider_led_tuple = led_range
        return
    
    def generate_full_manual_led_list(self)->list[tuple[int, int]]:
        """Returns a list of all LED ranges stored in this container as a list of tuples."""

        if self.slider_led_tuple:
            return list(itertools.chain.from_iterable([self.manual_led_tuple_list, [self.slider_led_tuple]]))
        return self.manual_led_tuple_list


class AutoLEDData:
    """Stores a LED range and brightness for a respective object when running a Object Detection Model."""
    def __init__(self, led_range: tuple[int, int], brightness: float):
        """A LED range and brightness which directly correlates to an object detected in the ObjectDetectionModel class.
        
        Parameters:
        - led_range (tuple[int, int]): A range of leds to illuminate.
        - brightness (float): The brightness level to illuminate this led range at."""
        self.led_range = led_range
        self.brightness = brightness    


class SystemLEDData:
    """Stores all LED Data relevant to a system, including ManualLEDData and AutoLEDData"""
    def __init__(self, manual_led_data: typing.Union[ManualLEDData, None], auto_led_data_list: typing.Union[list[AutoLEDData], None]):
        """Initializes attibutes used to store an instance of the ManualLEDData class, and a list of AutoLEDData instances.
        
        Parameters:
        - manual_led_data (typing.Union[ManualLEDData, None]): An instance of the ManualLEDData class used to store LED Data relevant to the GUI and the selections made on it.
        - auto_led_data_list (typing.Union[list[AutoLEDData], None]): A list of AutoLEDData instance to store LED data relevant to objects detected in the camera feed."""

        if manual_led_data:
            self.manual_led_data = manual_led_data
        else:
            self.manual_led_data = ManualLEDData()
        if auto_led_data_list:
            self.auto_led_data_list = auto_led_data_list    
        else:
            self.auto_led_data_list = []
        self.turn_off_leds: ManualLEDData = ManualLEDData()
        return
    
    def update_led_data_for_sending(self, auto_status: bool, manual_status: bool, num_of_leds: int = 256):
        """Called whenever data is being attempted to be sent over a socket connection to a server used to address the LEDs individually. This method will update the list of LEDs to be turned off and on, and at what respective
        brightness. Manually controlled LEDs are controlled with the same brightness, and are set to be never turned off, while AutoLED data is ignored if it is part of a manual LED range. Each AutoLED data instance contains
        its own brightness data, and so therefore these list can not be combined, but must be stored seperately in a list for sending over a socket connection. Lastly, this method generates a list of LED ranges that should be turned 
        off, and then stores this list in the list of list sent over the socket connection.
        
        Parameters:
        
        auto_status (bool): A boolean containing the state of the system, where true represents autonomous mode being enabled.
        manual_status (bool): A boolean containing the state of the system, where true represents Manual control mode being enabled.
        num_of_leds (int): The nummber of LEDs stored in a singular panel, but must be oreiented in the 32x8 style.
        """
        if auto_status and manual_status:
            self.full_manual_list = self.manual_led_data.generate_full_manual_led_list()
            if self.auto_led_data_list:
                full_led_list = list(itertools.chain.from_iterable([self.full_manual_list, [auto_led.led_range for auto_led in self.auto_led_data_list]]))
            else:
                full_led_list = self.full_manual_list
            missing_leds = find_missing_numbers_as_ranges_tuples(full_led_list, num_of_leds)
            self.turn_off_leds.manual_led_tuple_list = missing_leds
            self.auto_led_data_list = remove_overlapping_ranges_between_auto_led_and_manual_leds(self.full_manual_list, self.auto_led_data_list)
        elif manual_status:
            self.full_manual_list = self.manual_led_data.generate_full_manual_led_list()
            missing_leds = find_missing_numbers_as_ranges_tuples(self.full_manual_list, num_of_leds)
            self.turn_off_leds.manual_led_tuple_list = missing_leds
        elif auto_status:
            if self.auto_led_data_list:
                full_auto_list = [auto_led.led_range for auto_led in self.auto_led_data_list]
                if not full_auto_list:
                    missing_leds = (0, num_of_leds)
                else:
                    missing_leds = find_missing_numbers_as_ranges_tuples(full_auto_list, num_of_leds)
                self.turn_off_leds.manual_led_tuple_list = missing_leds
            else:
                missing_leds = (0, num_of_leds)
                full_auto_list = []
                self.turn_off_leds.manual_led_tuple_list = missing_leds
        return
    


def is_overlap(range1, range2):
    """Check if range1 overlaps with range2."""
    if (range1[0] < range2[1]) and (range1[1] > range2[0]):
        return True
    return False

def find_missing_numbers_as_ranges_tuples(ranges: list[tuple], all_numbers: int) -> typing.Union[list[tuple], None]:
    """Returns a list of tuples representing ranges that are not present in the ranges argument provide using the all_numbers arguement as the constrains for the range."""

    if not ranges:
        return [(0, all_numbers)]

    # Initialize a set with all numbers from 0 to 256
    all_numbers = set(range(all_numbers))
    
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
    

def remove_overlapping_ranges_between_auto_led_and_manual_leds(manual_led_tuple_list: list[tuple[int, int]], auto_led_data_list: list[AutoLEDData])->list[AutoLEDData]:
    """Updates the auto LED data range to not include data relevant to the manual ranges selected.
    
    Parameters:
    manual_led_tuple_list (list[tuple[int, int]]): A list of tuple ranges the user has selected in the GUI to be manually turned on.
    auto_led_data_list (list[AutoLEDData]): A list of AutoLEDData instances each representing a person detected in the current frame."""

    if not auto_led_data_list and not manual_led_tuple_list:
        return None
    elif not manual_led_tuple_list:
        return auto_led_data_list
    elif not auto_led_data_list:
        return None
    
    for led_range in manual_led_tuple_list:
        for auto_led in auto_led_data_list:
            if is_overlap(auto_led.led_range, led_range):
                auto_led.led_range = adjust_overlap(auto_led.led_range, led_range)
                if auto_led.led_range[0] == auto_led.led_range[1]:
                    auto_led_data_list.remove(auto_led)
    
    return auto_led_data_list


def adjust_overlap(range1: tuple[int, int], range2: tuple[int, int]):
    """
    Adjusts range1 to ensure there's no overlap with range2.
    :param range1 (tuple[int, int]): First range tuple.
    :param range2 (tuple[int, int]): Second range tuple.
    :return: Adjusted range1 tuple.
    """
    start1, end1 = range1
    start2, end2 = range2

    # Check if range1 completely overlaps range2 or vice versa
    if start1 >= start2 and end1 <= end2:
        return (start1, start1)  # Or any logic to handle complete overlap
    elif start2 >= start1 and end2 <= end1:
        return (start1, end2)  # Split range1 around range2

    # Partial overlap cases
    if start1 < start2 < end1 <= end2:
        return (start1, start2)  # Adjust end of range1 to start of range2
    elif start2 <= start1 < end2 < end1:
        return (end2, end1)  # Adjust start of range1 to end of range2

    # No overlap
    return range1

def focal_length_finder(camera_video_width: int, horizontal_fov: int)->float:
    """Using the width of the video from the camera in pixels and the horizontal field of view of the camera, both in pixels, this functuion returns the focal length in pixels of the camera."""
    fov_rad = math.radians(horizontal_fov)
    return camera_video_width / (2 * math.tan(fov_rad / 2))

if __name__ == '__main__':
    manual_led_data = ManualLEDData()
    manual_led_data.add_led_range((0, 32))
    # manual_led_data.add_led_range((32, 64))
    manual_led_data.add_led_range((96, 128))
    manual_led_data.set_slider_led_range((0, 70))
    auto_led_data_one = AutoLEDData((64, 96), .56)
    auto_led_data_two = AutoLEDData((0, 32), .51)
    auto_led_list = [auto_led_data_one,auto_led_data_two]
    system_led_data = SystemLEDData(manual_led_data, auto_led_list)
    print(f'System Led Data is: {[print(auto_led.led_range, auto_led.brightness) for auto_led in system_led_data.auto_led_data_list]}\n')
    system_led_data.update_led_data_for_sending(auto_status=True, manual_status=True)
    print(f"Updated LED Data is:")
    [print(auto_led.led_range, auto_led.brightness) for auto_led in system_led_data.auto_led_data_list if isinstance(auto_led, AutoLEDData)]
    print(f"System Manual Data is: {manual_led_data.manual_led_tuple_list} + {manual_led_data.slider_led_tuple}")
    print(f"System Turn Off Data is: {system_led_data.turn_off_leds.manual_led_tuple_list}")








