import PIL
from PIL import Image
import os

# doc = aw.Document()
# builder = aw.DocumentBuilder(doc)

# shape = builder.insert_image("Input.png")
# shape.get_shape_renderer().save("Output.png", aw.saving.ImageSaveOptions(aw.SaveFormat.PNG))


def get_all_jpg_files_in_directory(path: str)->list[str]:
    dir_contents = os.listdir(path)
    dir_contents_filtered = [os.path.join(path, file) for file in dir_contents if file.endswith('.jpg')]
    return dir_contents_filtered


def create_and_save_pngs_of_all_files_in_list(jpg_files: list[str])->None:
    for file in jpg_files:
        im = Image.open(file)
        im_resized = im.resize((720, 405))
        im_resized.save(file.replace('jpg', 'png'), "png")
    return

if __name__ == '__main__':
    pass