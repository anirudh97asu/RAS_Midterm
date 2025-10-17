import cv2
import numpy as np
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Tuple, Dict, List
from pydobot import Dobot

# ---------------- Configuration ----------------
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR.parent / "config" / "grid_configuration.json"
PNG_PATH = SCRIPT_DIR / "input" / "3x3_grid_opencv.png"
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

# Dobot positions
HOME_X, HOME_Y, HOME_Z, HOME_R = 232.09, -14.74, 129.59, 3.63
PEN_Z = -8.15
PORT = "/dev/ttyACM0"

# A4 dimensions in mm
A4_WIDTH_MM, A4_HEIGHT_MM = 210, 297


@dataclass
class GridParameters:
    """Configuration parameters for grid creation"""
    grid_size: int = 3
    margin: int = 10
    canvas_limit: int = 100
    
    @property
    def effective_size(self) -> int:
        """Calculate effective drawing area"""
        return self.canvas_limit - (2 * self.margin)
    
    @property
    def cell_size(self) -> int:
        """Calculate individual cell size"""
        return self.effective_size // self.grid_size
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "grid_size": self.grid_size,
            "effective_grid_size": self.effective_size,
            "cell_size": self.cell_size,
            "margin": self.margin,
            "cell_info": {}
        }


class GridConfiguration:
    """Manages grid cell configurations"""
    
    def __init__(self, params: GridParameters, start_x: float, start_y: float):
        self.params = params
        self.start_x = start_x + params.margin
        self.start_y = start_y + params.margin
        self.config = params.to_dict()
    
    def generate_cell_rectangles(self) -> Dict:
        """
        Generate cell rectangle coordinates.
        
        Grid numbering (row-major order):
        1 2 3
        4 5 6
        7 8 9
        
        Robot coordinate mapping:
        - Robot X = Traditional Y (horizontal)
        - Robot Y = Traditional X (vertical)
        
        Returns:
            Dictionary with cell configurations
        """
        counter = 1
        
        for row in range(self.params.grid_size):
            for col in range(self.params.grid_size):
                # Calculate cell boundaries
                x_min = self.start_x + col * self.params.cell_size
                x_max = self.start_x + (col + 1) * self.params.cell_size
                y_min = self.start_y + row * self.params.cell_size
                y_max = self.start_y + (row + 1) * self.params.cell_size
                
                # Store as [(x1, y1), (x2, y2)] - top-left to bottom-right
                self.config[f"cell_rectangle_{counter}"] = [
                    (x_min, y_min),
                    (x_max, y_max)
                ]
                counter += 1
        
        return self.config
    
    def save_to_file(self, filepath: Path):
        """Save configuration to JSON file"""
        with filepath.open("w") as f:
            json.dump(self.config, f, indent=4)


class DobotGridDrawer:
    """Handles physical grid drawing with Dobot"""
    
    def __init__(self, dobot: Dobot, params: GridParameters):
        self.dobot = dobot
        self.params = params
        self.home_pos = (HOME_X, HOME_Y, HOME_Z, HOME_R)
        self.start_x = HOME_X + params.margin
        self.start_y = HOME_Y + params.margin
    
    def move_home(self):
        """Return to home position"""
        self.dobot.move_to(*self.home_pos)
    
    def draw_line(self, x1: float, y1: float, x2: float, y2: float):
        """Draw a line from (x1, y1) to (x2, y2)"""
        self.move_home()
        self.dobot.move_to(x1, y1, PEN_Z, 0)
        self.dobot.move_to(x2, y2, PEN_Z, 0)
    
    def draw_grid(self):
        """Draw the complete grid"""
        print(f"Starting grid drawing at position: ({HOME_X}, {HOME_Y})")
        self.move_home()
        
        effective_size = self.params.effective_size
        
        # Draw all grid lines
        for i in range(self.params.grid_size + 1):
            offset = i * self.params.cell_size
            
            # Vertical line
            x = self.start_x + offset
            self.draw_line(x, self.start_y, x, self.start_y + effective_size)
            
            # Horizontal line
            y = self.start_y + offset
            self.draw_line(self.start_x, y, self.start_x + effective_size, y)
            
            print(f"Line {i+1}/{self.params.grid_size + 1} drawn")
        
        # Return to home
        self.move_home()
        print("Grid drawing complete")


class OpenCVGridDrawer:
    """Handles virtual grid drawing with OpenCV"""
    
    def __init__(self, params: GridParameters):
        self.params = params
        self.start_x = int(HOME_X + params.margin)
        self.start_y = int(HOME_Y + params.margin)
    
    def create_canvas(self) -> np.ndarray:
        """Create blank A4-sized canvas"""
        return np.ones((A4_HEIGHT_MM, A4_WIDTH_MM, 3), dtype=np.uint8) * 255
    
    def draw_grid(self) -> np.ndarray:
        """
        Draw grid on canvas matching Dobot configuration
        
        Returns:
            Canvas with drawn grid
        """
        canvas = self.create_canvas()
        effective_size = self.params.effective_size
        
        # Draw grid lines
        for i in range(self.params.grid_size + 1):
            offset = i * self.params.cell_size
            
            # Vertical line
            x = self.start_x + offset
            cv2.line(
                canvas,
                (x, self.start_y),
                (x, self.start_y + effective_size),
                (0, 0, 0),
                1
            )
            
            # Horizontal line
            y = self.start_y + offset
            cv2.line(
                canvas,
                (self.start_x, y),
                (self.start_x + effective_size, y),
                (0, 0, 0),
                1
            )
        
        # Draw A4 border
        cv2.rectangle(
            canvas,
            (0, 0),
            (A4_WIDTH_MM - 1, A4_HEIGHT_MM - 1),
            (0, 0, 0),
            2
        )
        
        return canvas
    
    def save_grid(self, filepath: Path) -> bool:
        """
        Draw and save grid to file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            grid_image = self.draw_grid()
            cv2.imwrite(str(filepath), grid_image)
            print(f"✓ Grid image saved to: {filepath}")
            return True
        except Exception as e:
            print(f"✗ Failed to save grid image: {e}")
            return False


def detect_dobot(port: str = PORT) -> Tuple[bool, Dobot | None]:
    """
    Attempt to connect to Dobot
    
    Returns:
        Tuple of (success, dobot_instance)
    """
    try:
        dobot = Dobot(port=port)
        print(f"✓ Dobot connected on port: {port}")
        return True, dobot
    except Exception as e:
        print(f"✗ Dobot not available: {e}")
        return False, None


def build_grid(port: str = PORT, params: GridParameters | None = None) -> str:
    """
    Main function to create grid and save configuration
    
    Args:
        port: Dobot serial port
        params: Grid parameters (uses defaults if None)
    
    Returns:
        String indicating which method was used: "dobot" or "opencv"
    """
    if params is None:
        params = GridParameters()
    
    # Attempt Dobot connection
    dobot_available, dobot = detect_dobot(port)
    
    # Draw grid based on available method
    if dobot_available:
        print("\n=== Drawing physical grid with Dobot ===")
        drawer = DobotGridDrawer(dobot, params)
        drawer.draw_grid()
        method = "dobot"
    else:
        print("\n=== Drawing virtual grid with OpenCV ===")
        drawer = OpenCVGridDrawer(params)
        drawer.save_grid(PNG_PATH)
        method = "opencv"
    
    # Generate and save cell configuration
    print("\n=== Generating cell configuration ===")
    grid_config = GridConfiguration(params, HOME_X, HOME_Y)
    grid_config.generate_cell_rectangles()
    grid_config.save_to_file(CONFIG_PATH)
    print(f"✓ Configuration saved to: {CONFIG_PATH}")
    
    # Cleanup
    if dobot:
        dobot.close()
        print("✓ Dobot connection closed")
    
    print(f"\n✓ Grid build complete using: {method.upper()}")
    return method


# Backward compatibility functions
def get_cell_configurations() -> Dict:
    """
    Legacy function for backward compatibility
    
    Returns:
        Grid configuration dictionary
    """
    params = GridParameters()
    grid_config = GridConfiguration(params, HOME_X, HOME_Y)
    return grid_config.generate_cell_rectangles()


def create_grid_using_dobot(dobot: Dobot):
    """
    Legacy function for backward compatibility
    """
    params = GridParameters()
    drawer = DobotGridDrawer(dobot, params)
    drawer.draw_grid()


def create_3x3_grid() -> np.ndarray:
    """
    Legacy function for backward compatibility
    
    Returns:
        Canvas with drawn grid
    """
    params = GridParameters()
    drawer = OpenCVGridDrawer(params)
    return drawer.draw_grid()


if __name__ == "__main__":
    # Run with default parameters
    build_grid()
    
    # Or run with custom parameters
    # custom_params = GridParameters(grid_size=3, margin=15, canvas_limit=120)
    # build_grid(params=custom_params)