import cv2
import numpy as np
import json
from pathlib import Path

from serial.tools import list_ports
from pydobot import Dobot
import copy

from pathlib import Path


# ---------------- Paths (Pathlib) ----------------
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = (SCRIPT_DIR.parent / "config" / "grid_configuration.json")
PNG_PATH = (SCRIPT_DIR / "input" / "3x3_grid_opencv.png")
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)  # ensure ../config exists


# dobot parameters
HOME_X = 232.09
HOME_Y = -14.74
HOME_Z = 129.59
HOME_R = 3.63

PEN_Z = -8.15


grid_configuration = {}

# port
port = "/dev/ttyACM0"  # identify and fix_port


# def get_cell_configurations():
#     grid_size = 3
#     START_X, START_Y = HOME_X, HOME_Y  # modify as per robot configurations
#     margin = 20
#     dobot_canvas_limit = 90
#     effective_size = dobot_canvas_limit - (2 * margin)
#     cell_size = effective_size // grid_size

#     grid_configuration["grid_size"] = grid_size
#     grid_configuration["effective_grid_size"] = effective_size
#     grid_configuration["cell_size"] = cell_size
#     grid_configuration["margin"] = margin
#     grid_configuration["cell_info"] = {}

#     START_X = START_X + margin
#     START_Y = START_Y + margin

#     counter = 1
#     for i in range(grid_size):
#         for j in range(grid_size):
#             grid_configuration[f"cell_rectangle_{counter}"] = [
#                 (START_X + i * cell_size, START_Y + j * cell_size),
#                 (START_X + (i + 1) * cell_size, START_Y + (j + 1) * cell_size),
#             ]
#             counter += 1

#     # for j in range(grid_size):      # j = row (Y direction)
#     #     for i in range(grid_size):  # i = column (X direction)
#     #         grid_configuration[f"cell_rectangle_{counter}"] = [
#     #             (START_X + i * cell_size, START_Y + j * cell_size),        # Top-left
#     #             (START_X + (i + 1) * cell_size, START_Y + (j + 1) * cell_size),  # Bottom-right
#     #         ]
#     #         counter += 1
    
#     # return grid_configuration

#     return grid_configuration

def get_cell_configurations():
    """
    Generate cell rectangles accounting for robot coordinate system:
    - Robot X = Traditional Y (horizontal)
    - Robot Y = Traditional X (vertical)
    """
    grid_size = 3
    START_X, START_Y = HOME_X, HOME_Y  # Robot coordinates
    
    # Use SAME values as in create_grid_using_dobot()
    margin = 10  # MUST MATCH the grid drawing function
    dobot_canvas_limit = 100  # MUST MATCH the grid drawing function
    
    effective_size = dobot_canvas_limit - (2 * margin)
    cell_size = effective_size // grid_size
    
    grid_configuration["grid_size"] = grid_size
    grid_configuration["effective_grid_size"] = effective_size
    grid_configuration["cell_size"] = cell_size
    grid_configuration["margin"] = margin
    grid_configuration["cell_info"] = {}
    
    # Apply margin to robot coordinates
    START_X = START_X + margin  # Robot X (traditional Y)
    START_Y = START_Y + margin  # Robot Y (traditional X)
    
    counter = 1
    # Grid numbering (row-major, traditional view):
    # 1 2 3
    # 4 5 6  
    # 7 8 9

    
    for row in range(grid_size):      # row = traditional rows (top to bottom)
        for col in range(grid_size):  # col = traditional columns (left to right)
            # In robot coordinates:
            # - col affects robot-X (traditional Y, horizontal position)
            # - row affects robot-Y (traditional X, vertical position)
            
            robot_x_min = START_X + col * cell_size      # Left edge in traditional view
            robot_x_max = START_X + (col + 1) * cell_size  # Right edge
            robot_y_min = START_Y + row * cell_size      # Top edge in traditional view
            robot_y_max = START_Y + (row + 1) * cell_size  # Bottom edge
            
            # Store as [(robot_x1, robot_y1), (robot_x2, robot_y2)]
            grid_configuration[f"cell_rectangle_{counter}"] = [
                (robot_x_min, robot_y_min),  # Top-left in traditional view
                (robot_x_max, robot_y_max),  # Bottom-right in traditional view
            ]
            counter += 1
    
    return grid_configuration


def create_grid_using_dobot(dobot):
    # A4 size: 210 mm width x 297 mm height
    # In our dobot case x-> height and y -> width

    dobot.move_to(HOME_X, HOME_Y, HOME_Z, HOME_R)

    print("HOME", HOME_X, HOME_Y, HOME_Z, HOME_R)

    grid_size = 3
    START_X, START_Y = HOME_X, HOME_Y  # Fix this from dobot.get_position()
    margin = 10  # 25mm
    dobot_canvas_limit = 100
    effective_size = dobot_canvas_limit - (2 * margin)
    cell_size = effective_size // grid_size

    if dobot is not None:
        
        START_X = START_X + margin
        START_Y = START_Y + margin

        for i in range(grid_size + 1):
            
            NEW_X = START_X + i * cell_size
            NEW_Y = START_Y + i * cell_size

            print(START_X, START_Y, NEW_X, NEW_Y)


            # move/draw vertical
            dobot.move_to(HOME_X, HOME_Y, HOME_Z, HOME_R)
            dobot.move_to(NEW_X, START_Y, PEN_Z, 0)
            dobot.move_to(NEW_X, START_Y + effective_size, PEN_Z, 0)
            # move/draw horizontal
            dobot.move_to(HOME_X, HOME_Y, HOME_Z, HOME_R)
            dobot.move_to(START_X, NEW_Y, PEN_Z, 0)
            dobot.move_to((START_X + effective_size), NEW_Y, PEN_Z, 0)

        # return to home position
        dobot.move_to(HOME_X, HOME_Y, HOME_Z, HOME_R)

    return


def create_3x3_grid():
    """
    Create a clean 3x3 grid on A4-sized canvas using OpenCV
    Canvas dimensions represent actual A4 size in mm: 210mm x 297mm
    """
    # A4 dimensions in mm
    A4_WIDTH_MM = 210
    A4_HEIGHT_MM = 297

    # Create canvas with A4 dimensions (1 pixel = 1 mm)
    canvas_width = A4_WIDTH_MM
    canvas_height = A4_HEIGHT_MM
    canvas = np.ones((canvas_height, canvas_width, 3), dtype=np.uint8) * 255

    # Grid parameters matching Dobot configuration exactly
    grid_size = 3
    START_X_MM, START_Y_MM = HOME_X, HOME_Y  # Same as Dobot start positions
    MARGIN_MM = 20  # Same as Dobot margin
    DOBOT_CANVAS_LIMIT_MM = 120  # Same as Dobot canvas limit

    # Calculate effective size and cell size (same calculations as Dobot)
    effective_size_mm = DOBOT_CANVAS_LIMIT_MM - (2 * MARGIN_MM)  # 80mm
    cell_size_mm = effective_size_mm // grid_size  # 26mm

    # Apply margin to start positions (same as Dobot)
    START_X = START_X_MM + MARGIN_MM
    START_Y = START_Y_MM + MARGIN_MM

    # Draw grid lines
    for i in range(grid_size + 1):
        # Vertical lines
        x = START_X + i * cell_size_mm
        cv2.line(canvas, (x, START_Y), (x, START_Y + effective_size_mm), (0, 0, 0), 1)

        # Horizontal lines
        y = START_Y + i * cell_size_mm
        cv2.line(canvas, (START_X, y), (START_X + effective_size_mm, y), (0, 0, 0), 1)

        print(x, y)

    # Draw A4 border
    cv2.rectangle(canvas, (0, 0), (A4_WIDTH_MM - 1, A4_HEIGHT_MM - 1), (0, 0, 0), 2)

    return canvas


def build_grid():
    """
    Main function to create and save the grid
    """
    scheduler = None
    dobot = None
    try:
        dobot = Dobot(port=port)
        print(f"✓ Real Dobot connected on port: {port}")
        scheduler = "dobot"
    except Exception:
        scheduler = "opencv"

    if scheduler == "opencv":
        grid_image = create_3x3_grid()
        # Use pathlib path (convert to str for OpenCV)
        cv2.imwrite(str(PNG_PATH), grid_image)
    else:  # "dobot"
        create_grid_using_dobot(dobot)

    # Save grid configuration using pathlib
    get_cell_configurations()
    with CONFIG_PATH.open("w") as f:
        json.dump(grid_configuration, f, indent=4)

    if dobot:
        #dobot.move_to(HOME_X, HOME_Y, HOME_Z, HOME_R)
        dobot.close()
    
    return scheduler


if __name__ == "__main__":
    build_grid()
