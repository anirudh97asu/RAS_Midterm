import json
import time
from math import cos, sin, pi
from pathlib import Path
from typing import Tuple, Optional
from dataclasses import dataclass
from contextlib import contextmanager
from pydobot import Dobot

# ---------------- Configuration ----------------
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR.parent / "config" / "grid_configuration.json"
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

# Cell mapping: visual position -> config key
CELL_MAPPING = {
    1: "rectangle_cell_1", 2: "rectangle_cell_4", 3: "rectangle_cell_7",
    4: "rectangle_cell_2", 5: "rectangle_cell_5", 6: "rectangle_cell_8",
    7: "rectangle_cell_3", 8: "rectangle_cell_6", 9: "rectangle_cell_9"
}


@dataclass
class DobotPosition:
    """Represents a Dobot position"""
    x: float
    y: float
    z: float
    r: float
    
    def as_tuple(self) -> Tuple[float, float, float, float]:
        """Return position as tuple"""
        return (self.x, self.y, self.z, self.r)


@dataclass
class DrawConfig:
    """Configuration for drawing operations"""
    home: DobotPosition
    z_draw: float
    z_lift: float
    inset: float
    symbol_margin: float
    
    @property
    def z_travel(self) -> float:
        """Calculate travel height"""
        return self.z_draw + self.z_lift


class DobotMotionController:
    """Handles low-level Dobot motion commands"""
    
    MOVJ_XYZ = 1  # Joint move mode
    MOVL_XYZ = 2  # Linear move mode
    
    def __init__(self, dobot: Dobot, config: DrawConfig):
        self.dobot = dobot
        self.config = config
    
    def _wait(self):
        """Wait for current command to complete"""
        try:
            if hasattr(self.dobot, 'wait'):
                self.dobot.wait()
            else:
                time.sleep(0.3)
        except Exception:
            time.sleep(0.3)
    
    def move_linear(self, x: float, y: float, z: float, r: Optional[float] = None):
        """Linear move (for drawing)"""
        if r is None:
            r = self.config.home.r
        
        if hasattr(self.dobot, "_set_ptp_cmd"):
            self.dobot._set_ptp_cmd(x, y, z, r, mode=self.MOVL_XYZ)
        else:
            self.dobot.move_to(x, y, z, r)
        self._wait()
    
    def move_joint(self, x: float, y: float, z: float, r: Optional[float] = None):
        """Joint move (for safe travels)"""
        if r is None:
            r = self.config.home.r
        
        if hasattr(self.dobot, "_set_ptp_cmd"):
            self.dobot._set_ptp_cmd(x, y, z, r, mode=self.MOVJ_XYZ)
        else:
            self.dobot.move_to(x, y, z, r)
        self._wait()
    
    def move_arc(self, via_x: float, via_y: float, via_z: float,
                 end_x: float, end_y: float, end_z: float, r: Optional[float] = None):
        """Arc move from current position through via point to end point"""
        if r is None:
            r = self.config.home.r
        
        if hasattr(self.dobot, "_set_arc_cmd"):
            self.dobot._set_arc_cmd(via_x, via_y, via_z, r, end_x, end_y, end_z, r)
        elif hasattr(self.dobot, "arc_to"):
            self.dobot.arc_to(via_x, via_y, via_z, r, end_x, end_y, end_z, r)
        else:
            raise RuntimeError("ARC command not available in this driver")
        self._wait()
    
    def get_current_position(self) -> Tuple[float, float, float, float]:
        """Get current position or return home as fallback"""
        try:
            pose = self.dobot.get_pose()
            return tuple(float(p) for p in pose[:4])
        except Exception as e:
            print(f"Warning: Could not get current pose: {e}")
            return self.config.home.as_tuple()
    
    def pen_up(self, x: Optional[float] = None, y: Optional[float] = None, 
               r: Optional[float] = None):
        """Lift pen to travel height"""
        if x is None or y is None:
            cx, cy, _, cr = self.get_current_position()
            x = x if x is not None else cx
            y = y if y is not None else cy
            r = r if r is not None else cr
        
        if r is None:
            r = self.config.home.r
        
        self.move_joint(x, y, self.config.z_travel, r)
    
    def pen_down(self, x: float, y: float, r: Optional[float] = None):
        """Lower pen to drawing height"""
        if r is None:
            r = self.config.home.r
        
        # Move above target first, then descend
        self.move_joint(x, y, self.config.z_travel, r)
        self.move_linear(x, y, self.config.z_draw, r)
    
    def go_home(self, safe: bool = True):
        """Return to home position"""
        try:
            if safe:
                self.pen_up()
            
            home = self.config.home
            self.move_joint(home.x, home.y, self.config.z_travel, home.r)
            self.move_joint(home.x, home.y, home.z, home.r)
            print("✓ Reached home position")
        except Exception as e:
            print(f"Error in go_home: {e}")
            # Fallback: single move
            try:
                self.dobot.move_to(*self.config.home.as_tuple())
                self._wait()
            except Exception as e2:
                print(f"Fallback home move failed: {e2}")


class SymbolDrawer:
    """Handles drawing of X and O symbols"""
    
    def __init__(self, motion: DobotMotionController):
        self.motion = motion
    
    def draw_circle_linear(self, cx: float, cy: float, radius: float, segments: int = 64):
        """Draw circle using linear segments"""
        dth = 2.0 * pi / segments
        
        # Start at 0 degrees
        x0, y0 = cx + radius, cy
        self.motion.pen_down(x0, y0)
        
        # Draw segments
        for i in range(1, segments + 1):
            th = i * dth
            x = cx + radius * cos(th)
            y = cy + radius * sin(th)
            self.motion.move_linear(x, y, self.motion.config.z_draw)
        
        # Lift at end
        self.motion.pen_up(x0, y0)
    
    def draw_circle_arc(self, cx: float, cy: float, radius: float):
        """Draw circle using two 180° arcs (with linear fallback)"""
        # Key positions
        x0, y0 = cx + radius, cy        # 0°
        x90, y90 = cx, cy + radius      # 90°
        x180, y180 = cx - radius, cy    # 180°
        x270, y270 = cx, cy - radius    # 270°
        z = self.motion.config.z_draw
        
        try:
            # Draw as two semicircles
            self.motion.pen_down(x0, y0)
            self.motion.move_arc(x90, y90, z, x180, y180, z)  # 0° -> 180°
            self.motion.move_arc(x270, y270, z, x0, y0, z)    # 180° -> 360°
            self.motion.pen_up(x0, y0)
        except Exception:
            print("Arc not available, using linear approximation")
            self.draw_circle_linear(cx, cy, radius)
    
    def draw_x(self, cx: float, cy: float, width: float, height: Optional[float] = None):
        """Draw X using two diagonals"""
        if height is None:
            height = width
        
        # Calculate corners
        hw, hh = width / 2.0, height / 2.0
        left, right = cx - hw, cx + hw
        bottom, top = cy - hh, cy + hh
        
        # Diagonal 1: top-left to bottom-right
        self.motion.pen_down(left, top)
        self.motion.move_linear(right, bottom, self.motion.config.z_draw)
        self.motion.pen_up(right, bottom)
        
        # Diagonal 2: bottom-left to top-right
        self.motion.pen_down(left, bottom)
        self.motion.move_linear(right, top, self.motion.config.z_draw)
        self.motion.pen_up(right, top)


class GridCellCalculator:
    """Calculates safe drawing areas within grid cells"""
    
    def __init__(self, config_data: dict, draw_config: DrawConfig):
        self.config_data = config_data
        self.draw_config = draw_config
    
    def get_cell_rect(self, cell_number: int) -> Tuple[float, float, float, float]:
        """Get cell rectangle bounds (left, top, right, bottom)"""
        # Map cell number to config key
        cfg_key = CELL_MAPPING[cell_number]
        cfg_key = "cell_" + cfg_key.replace("_cell", "")
        
        # Extract coordinates
        (x1, y1), (x2, y2) = self.config_data[cfg_key]
        return float(x1), float(y1), float(x2), float(y2)
    
    def get_safe_drawing_area(self, cell_number: int) -> Tuple[float, float, float, float]:
        """
        Calculate safe drawing area for a cell.
        
        Returns:
            Tuple of (center_x, center_y, half_width, half_height)
        """
        left, top, right, bottom = self.get_cell_rect(cell_number)
        
        # Apply inset to avoid grid lines
        left += self.draw_config.inset
        top += self.draw_config.inset
        right -= self.draw_config.inset
        bottom -= self.draw_config.inset
        
        # Calculate center
        cx = (left + right) / 2.0
        cy = (top + bottom) / 2.0
        
        # Calculate safe half-dimensions with symbol margin
        hw = max((right - left) / 2.0 - self.draw_config.symbol_margin, 0.1)
        hh = max((bottom - top) / 2.0 - self.draw_config.symbol_margin, 0.1)
        
        return cx, cy, hw, hh


class DrawModule:
    """Main interface for drawing symbols on the grid"""
    
    def __init__(self, port: str, config_path: Path, home_x: float, home_y: float,
                 home_z: float, home_r: float, z_draw: float = -15.0, z_lift: float = 20.0,
                 inset: float = 2.0, symbol_margin: float = 1.5):
        """
        Initialize draw module.
        
        Args:
            port: Dobot serial port
            config_path: Path to grid configuration JSON
            home_x, home_y, home_z, home_r: Home position coordinates
            z_draw: Drawing (pen-down) height
            z_lift: Clearance above z_draw for travel moves
            inset: Distance to stay inside cell boundaries
            symbol_margin: Extra safety margin from cell edges
        """
        self.port = port
        self.dobot = None
        
        # Load configuration
        with open(config_path, "r") as f:
            self.grid_config = json.load(f)
        
        # Setup drawing configuration
        home = DobotPosition(
            x=float(home_x),
            y=float(home_y),
            z=float(home_z),
            r=float(home_r)
        )
        
        self.draw_config = DrawConfig(
            home=home,
            z_draw=float(z_draw),
            z_lift=float(z_lift),
            inset=float(inset),
            symbol_margin=float(symbol_margin)
        )
        
        self.cell_calc = GridCellCalculator(self.grid_config, self.draw_config)
    
    @contextmanager
    def _connection(self):
        """Context manager for Dobot connection"""
        try:
            print(f"Connecting to Dobot on {self.port}...")
            self.dobot = Dobot(port=self.port)
            time.sleep(0.5)
            
            # Set modest speeds if supported
            try:
                self.dobot._set_ptp_common_params(velocity=50, acceleration=50)
            except Exception:
                pass
            
            print("✓ Dobot connected")
            yield self.dobot
            
        finally:
            if self.dobot:
                try:
                    print("Disconnecting Dobot...")
                    time.sleep(1.0)
                    self.dobot.close()
                    print("✓ Dobot disconnected")
                except Exception as e:
                    print(f"Error during disconnect: {e}")
                finally:
                    self.dobot = None
                    time.sleep(2.0)
    
    def draw(self, rectangle_number: int, dobot_symbol: str) -> bool:
        """
        Draw X or O in specified cell.
        
        Args:
            rectangle_number: Cell number (1-9)
            dobot_symbol: Symbol to draw ('X' or 'O')
        
        Returns:
            True if successful, False otherwise
        """
        if rectangle_number not in range(1, 10):
            raise ValueError("rectangle_number must be between 1 and 9")
        
        symbol = dobot_symbol.upper()
        if symbol not in ['X', 'O']:
            raise ValueError("dobot_symbol must be 'X' or 'O'")
        
        try:
            with self._connection() as dobot:
                motion = DobotMotionController(dobot, self.draw_config)
                drawer = SymbolDrawer(motion)
                
                print(f"Drawing '{symbol}' in cell {rectangle_number}")
                
                # Move to home
                print("Moving to home position...")
                dobot.move_to(*self.draw_config.home.as_tuple())
                time.sleep(0.5)
                print("✓ At home position")
                
                # Get safe drawing area
                cx, cy, hw, hh = self.cell_calc.get_safe_drawing_area(rectangle_number)
                print(f"Drawing at center: ({cx:.2f}, {cy:.2f})")
                
                # Draw symbol
                if symbol == 'O':
                    radius = max(0.98 * min(hw, hh), 0.2)
                    print(f"Drawing O with radius {radius:.2f}mm")
                    drawer.draw_circle_arc(cx, cy, radius)
                else:  # X
                    width, height = 2.0 * hw, 2.0 * hh
                    print(f"Drawing X with dimensions {width:.2f}mm x {height:.2f}mm")
                    drawer.draw_x(cx, cy, width, height)
                
                print("✓ Drawing complete")
                time.sleep(2.0)
                
                # Return home
                print("Returning to home position...")
                motion.go_home(safe=True)
                time.sleep(2.0)
                
                return True
                
        except Exception as e:
            print(f"Error during drawing: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def close(self):
        """Cleanup method"""
        if self.dobot:
            try:
                self.dobot.close()
            except Exception:
                pass
            finally:
                self.dobot = None
    
    def __del__(self):
        """Destructor"""
        self.close()


# Backward compatibility alias
draw_module = DrawModule


if __name__ == "__main__":
    # Configuration
    port = "/dev/ttyACM0"
    home_x, home_y, home_z, home_r = 232.09, -14.74, 129.59, 3.63
    pen_z = -5.15
    
    # Create drawer
    dm = DrawModule(
        port=port,
        config_path=CONFIG_PATH,
        home_x=home_x,
        home_y=home_y,
        home_z=home_z,
        home_r=home_r,
        z_draw=pen_z,
        z_lift=20.0,
        inset=2.0,
        symbol_margin=1.5
    )
    
    # Test drawing
    success = dm.draw(rectangle_number=1, dobot_symbol="x")
    print(f"Draw operation {'succeeded' if success else 'failed'}")
    
    success = dm.draw(rectangle_number=5, dobot_symbol="o")
    print(f"Draw operation {'succeeded' if success else 'failed'}")
    
    dm.close()