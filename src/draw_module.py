# pip install pydobot2 pyserial
import json
from math import cos, sin, pi
from pathlib import Path
from pydobot import Dobot
import time


cell_mapping = {1: "rectangle_cell_1",
                2: "rectangle_cell_4",
                3: "rectangle_cell_7",
                4: "rectangle_cell_2",
                5: "rectangle_cell_5",
                6: "rectangle_cell_8",
                7: "rectangle_cell_3",
                8: "rectangle_cell_6",
                9: "rectangle_cell_9"}


# ---------------- Paths (Pathlib) ----------------
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = (SCRIPT_DIR.parent / "config" / "grid_configuration.json")
PNG_PATH = (SCRIPT_DIR / "input" / "3x3_grid_opencv.png")
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)  # ensure ../config exists


class draw_module:
    """Draw X / O inside YOLO-style rectangles (mm), staying clear of grid lines."""
    MOVJ_XYZ, MOVL_XYZ = 1, 2  # Dobot PTP modes (joint / linear)

    def __init__(
        self,
        port,
        config_path,
        *,
        HOME_X,
        HOME_Y,
        HOME_Z,
        HOME_R,
        z_draw=-15.0,
        z_lift=20.0,
        inset=2.0,
        symbol_margin=1.5,  # extra safety margin inside each (already inset) cell
    ):
        # Store port for later connection
        self.port = port
        self.bot = None  # No connection yet

        with open(config_path, "r") as f:
            self.cfg = json.load(f)

        # store home & pen heights on the instance (avoid globals)
        # Ensure all values are floats
        try:
            self.home_x = float(HOME_X)
            self.home_y = float(HOME_Y)
            self.home_z = float(HOME_Z)
            self.home_r = float(HOME_R)
        except (ValueError, TypeError) as e:
            raise ValueError(f"HOME_X, HOME_Y, HOME_Z, HOME_R must be numeric values. Error: {e}")

        # drawing heights and geometry
        self.z_draw = float(z_draw)   # pen-down (drawing) height
        self.z_lift = float(z_lift)   # clearance added above z_draw for travels
        self.inset = float(inset)     # shrink inside cell so we don't touch borders
        self.symbol_margin = float(symbol_margin)  # extra gap from cell edges

    def _connect(self):
        """Connect to the Dobot."""
        if self.bot is None:
            print(f"Connecting to Dobot on port {self.port}...")
            self.bot = Dobot(port=self.port)
            time.sleep(0.5)  # Give hardware time to initialize
            print("Dobot connected successfully")
            
            # optional: set modest speeds (ignore errors if FW/lib doesn't expose it)
            try:
                self.bot._set_ptp_common_params(velocity=50, acceleration=50)
            except Exception:
                pass
    
    def _wait_for_command(self):
        """Wait for the current command to complete."""
        try:
            if hasattr(self.bot, 'wait'):
                self.bot.wait()
            else:
                # Fallback: wait a bit for command to execute
                time.sleep(0.3)
        except Exception:
            time.sleep(0.3)

    def _disconnect(self):
        """Disconnect from the Dobot."""
        if self.bot is not None:
            try:
                print("Disconnecting from Dobot...")
                # Wait for any pending commands to complete
                time.sleep(1.0)
                self.bot.close()
                print("Dobot disconnected successfully")
            except Exception as e:
                print(f"Error during disconnect: {e}")
            finally:
                self.bot = None
                time.sleep(2.0)  # Give hardware time to fully reset before next connection

    # -------------------- low-level motion helpers --------------------
    def _ptp_linear(self, x, y, z, r=None):
        """Linear move (used while drawing)."""
        if r is None:
            r = self.home_r
        if hasattr(self.bot, "_set_ptp_cmd"):
            self.bot._set_ptp_cmd(x, y, z, r, mode=self.MOVL_XYZ)
        else:
            self.bot.move_to(x, y, z, r)
        self._wait_for_command()

    def _arc_cmd(self, vx, vy, vz, ex, ey, ez, r=None):
        """Send a single arc (start = current pose) via 'via' point -> 'end' point."""
        if r is None:
            r = self.home_r
        # Try common Dobot arc APIs, else raise
        if hasattr(self.bot, "_set_arc_cmd"):                # many pydobot forks
            self.bot._set_arc_cmd(vx, vy, vz, r, ex, ey, ez, r)
        elif hasattr(self.bot, "arc_to"):                    # some wrappers
            self.bot.arc_to(vx, vy, vz, r, ex, ey, ez, r)
        else:
            raise RuntimeError("ARC command not available in this driver")
        self._wait_for_command()

    def _ptp_joint(self, x, y, z, r=None):
        """Joint move (used for safe travels, lifts, homing)."""
        if r is None:
            r = self.home_r
        if hasattr(self.bot, "_set_ptp_cmd"):
            self.bot._set_ptp_cmd(x, y, z, r, mode=self.MOVJ_XYZ)
        else:
            self.bot.move_to(x, y, z, r)
        self._wait_for_command()

    def _pen_up(self, x=None, y=None, r=None):
        """Lift to travel height at current or specified XY."""
        if r is None:
            r = self.home_r
        if x is None or y is None:
            try:
                pose = self.bot.get_pose()
                cx, cy, cz, cr = float(pose[0]), float(pose[1]), float(pose[2]), float(pose[3])
                x = cx if x is None else float(x)
                y = cy if y is None else float(y)
                r = float(cr)
            except Exception as e:
                print(f"Warning: Could not get current pose: {e}")
                # Use home position as fallback
                x = self.home_x if x is None else float(x)
                y = self.home_y if y is None else float(y)
                r = self.home_r if r is None else float(r)
        
        # Ensure all values are floats
        x, y, r = float(x), float(y), float(r)
        self._ptp_joint(x, y, self.z_draw + self.z_lift, r)

    def _pen_down(self, x, y, r=None):
        """Descend to drawing height linearly at XY."""
        if r is None:
            r = self.home_r
        # ensure we're above before going down
        self._ptp_joint(x, y, self.z_draw + self.z_lift, r)
        self._ptp_linear(x, y, self.z_draw, r)

    def go_home(self, *, safe=True):
        """Return to HOME; if safe=True, lift first."""
        try:
            if safe:
                self._pen_up()
            # travel above HOME, then down to HOME_Z
            self._ptp_joint(self.home_x, self.home_y, self.z_draw + self.z_lift, self.home_r)
            self._ptp_joint(self.home_x, self.home_y, self.home_z, self.home_r)
            print("Reached home position")
        except Exception as e:
            print(f"Error in go_home: {e}")
            import traceback
            traceback.print_exc()
            # last resort: try a single move
            try:
                self.bot.move_to(self.home_x, self.home_y, self.home_z, self.home_r)
                self._wait_for_command()
            except Exception as e2:
                print(f"Fallback home move also failed: {e2}")

    # -------------------- config helpers (rects already in mm) --------------------
    def _rect(self, n: int):
        """Return L, T, R, B in mm."""
        cfg_map = cell_mapping[n]
        cfg_map = "cell_" + cfg_map.replace("_cell", "")
        (x1, y1), (x2, y2) = self.cfg[cfg_map]  # TL, BR
        x1 = x1 
        x2 = x2 
        y1 = y1
        y2 = y2 
        L, T, R, B = float(x1), float(y1), float(x2), float(y2)
        return L, T, R, B

    def _center_size(self, rect):
        L, T, R, B = rect
        L, T, R, B = L + self.inset, T + self.inset, R - self.inset, B - self.inset
        cx, cy = (L + R) / 2.0, (T + B) / 2.0
        return cx, cy, (R - L), (B - T)

    def _safe_box(self, rect):
        """
        From a rect, return center and safe half-width/half-height after both inset and symbol_margin.
        Ensures we keep a clear gap from the grid lines, accounting for pen width/backlash.
        """
        cx, cy, iw, ih = self._center_size(rect)
        # Safe half-dimensions: back off by symbol_margin from each edge
        hw = max(iw / 2.0 - self.symbol_margin, 0.1)
        hh = max(ih / 2.0 - self.symbol_margin, 0.1)
        return cx, cy, hw, hh

    #-------------------- primitives --------------------
    def _draw_o(self, cx, cy, radius):
        """Robust O using linear segments."""
        segs = 64  # 48–72 is a good range; 64 is smooth & quick
        dth = 2.0 * pi / segs

        # start at angle 0
        x0, y0 = cx + radius, cy

        # go above start and pen down
        self._pen_down(x0, y0)

        # draw the loop
        for i in range(1, segs + 1):
            th = i * dth
            x = cx + radius * cos(th)
            y = cy + radius * sin(th)
            self._ptp_linear(x, y, self.z_draw, self.home_r)

        # lift at the close point
        self._pen_up(x0, y0)

    def _draw_o_arc(self, cx, cy, radius, *, prefer_arcs=True):
        """Draw an 'O' with two 180° arcs when available; otherwise linear segments."""
        x0,  y0  = cx + radius, cy        # 0°
        x90, y90 = cx, cy + radius        # 90°
        x180,y180= cx - radius, cy        # 180°
        x270,y270= cx, cy - radius        # 270°
        z = self.z_draw
        r = self.home_r

        if prefer_arcs:
            try:
                # move to 0°, pen down
                self._pen_down(x0, y0, r)
                # CCW semicircle: 0° -> 180° via 90°
                self._arc_cmd(x90, y90, z, x180, y180, z, r)
                # CCW semicircle: 180° -> 360° via 270°
                self._arc_cmd(x270, y270, z, x0, y0, z, r)
                self._pen_up(x0, y0, r)
                return
            except Exception:
                # fall back to linear approximation below
                print("Arc not working, using linear approximation")

        # Fallback: many short linear segments (always works)
        segs = 64
        dth = 2.0 * pi / segs
        self._pen_down(x0, y0, r)
        for i in range(1, segs + 1):
            th = i * dth
            self._ptp_linear(cx + radius * cos(th), cy + radius * sin(th), z, r)
        self._pen_up(x0, y0, r)

    def _draw_x(self, cx, cy, w, h=None):
        """Two diagonals inside the shrunken cell; always lifts before/after."""
        if h is None:
            h = w
        xL, xR = cx - w / 2.0 , cx + w / 2.0
        yB, yT = cy - h / 2.0, cy + h / 2.0

        # Diagonal 1: TL -> BR
        self._pen_down(xL, yT)
        self._ptp_linear(xR, yB, self.z_draw, self.home_r)
        self._pen_up(xR, yB)

        # Diagonal 2: BL -> TR
        self._pen_down(xL, yB)
        self._ptp_linear(xR, yT, self.z_draw, self.home_r)
        self._pen_up(xR, yT)

    # -------------------- public API --------------------
    def draw(self, rectangle_number: int, dobot_symbol: str):
        """
        Draw 'X' or 'O' in the given cell (1..9). 
        Connects to Dobot, draws, returns to HOME, and disconnects.
        """
        flag = False
        
        try:
            # Connect to the Dobot
            self._connect()
            
            print(f"Drawing '{dobot_symbol}' in cell {rectangle_number}")
            
            # Move to home position
            print("Moving to home position...")
            self.bot.move_to(self.home_x, self.home_y, self.home_z, self.home_r)
            self._wait_for_command()
            print("At home position")
            
            # Get safe drawing area
            cx, cy, hw, hh = self._safe_box(self._rect(rectangle_number))
            print(f"Drawing at center: ({cx:.2f}, {cy:.2f})")

            if dobot_symbol.upper() == "O":
                # Slightly reduce to add extra cushion inside the safe box
                radius = max(0.98 * min(hw, hh), 0.2)
                print(f"Drawing O with radius {radius:.2f}mm")
                self._draw_o_arc(cx, cy, radius)
                flag = True
            elif dobot_symbol.upper() == "X":
                print(f"Drawing X with dimensions {2.0*hw:.2f}mm x {2.0*hh:.2f}mm")
                # Use full safe width/height so it stays inside and off the grid
                self._draw_x(cx, cy, w=2.0 * hw, h=2.0 * hh)
                flag = True
            else:
                raise ValueError("dobot_symbol must be 'X' or 'O'")
            
            print("Drawing complete! Waiting for all movements to finish...")
            # Extra wait to ensure all queued commands complete
            time.sleep(2.0)
                
        except Exception as e:
            print(f"Error during drawing: {e}")
            import traceback
            traceback.print_exc()
            flag = False
        finally:
            # ALWAYS return to HOME and disconnect, even if something fails mid-draw
            try:
                print("Returning to home position...")
                self.go_home(safe=True)
                print("Waiting for return to home to complete...")
                time.sleep(2.0)  # Wait for return home to complete
            except Exception as e:
                print(f"Error returning home: {e}")
            finally:
                self._disconnect()
        
        return flag

    def close(self):
        """Cleanup method - ensures disconnection."""
        self._disconnect()

    def __del__(self):
        """Destructor - ensures disconnection on object deletion."""
        self.close()


if __name__ == "__main__":
    port = "/dev/ttyACM0"
    # dobot parameters
    HOME_X = 232.09
    HOME_Y = -14.74 
    HOME_Z = 129.59
    HOME_R = 3.63

    PEN_Z = -5.15

    dm = draw_module(
        port=port,
        config_path=CONFIG_PATH,
        HOME_X=HOME_X,
        HOME_Y=HOME_Y,
        HOME_Z=HOME_Z,
        HOME_R=HOME_R,
        z_draw=PEN_Z,    # pen-down height (adjust for your pen/tool)
        z_lift=20.0,     # clearance above z_draw for moves
        inset=2.0,       # stay inside the box a bit
        symbol_margin=1.5  # extra safety margin to avoid touching grid lines
    )
    
    # Draw X in cell 1
    success = dm.draw(rectangle_number=1, dobot_symbol="x")
    print(f"Draw operation {'succeeded' if success else 'failed'}")
    
    # Draw O in cell 5
    success = dm.draw(rectangle_number=5, dobot_symbol="o")
    print(f"Draw operation {'succeeded' if success else 'failed'}")

    dm.close()