import google.generativeai as genai
from PIL import Image
import cv2
import os
import sys
import json
import time
from pathlib import Path
from pydobot import Dobot
from dotenv import load_dotenv

# Add src directory to path
src_path = Path(__file__).parent
sys.path.insert(0, str(src_path))

# ---------------- Configuration ----------------
# Dobot positions
POSITIONS = {
    'home': {'x': 232.09, 'y': -14.74, 'z': 129.59, 'r': 3.63},
    'camera': {'x': 210.93, 'y': 20.34, 'z': 0, 'r': 6.49},
    'pen_z': -5.15
}

PORT = "/dev/ttyACM0"

# Model configuration
DEFAULT_MODEL = 'gemini-2.5-flash'
FALLBACK_MODEL = 'gemini-1.5-flash'


class DobotController:
    """Manages Dobot movements"""
    
    def __init__(self, port=PORT):
        self.port = port
        self.dobot = None
    
    def __enter__(self):
        """Context manager entry"""
        self.dobot = Dobot(port=self.port)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.dobot:
            self.move_to_home()
            self.dobot.close()
    
    def move_to_position(self, position_name):
        """Move to a predefined position"""
        pos = POSITIONS[position_name]
        self.dobot.move_to(pos['x'], pos['y'], pos['z'], pos['r'])
    
    def move_to_home(self):
        """Move to home position"""
        self.move_to_position('home')
    
    def move_to_camera(self):
        """Move to camera position"""
        self.move_to_position('camera')


class GeminiVisionAPI:
    """Handles Gemini API interactions"""
    
    def __init__(self, api_key=None, model_name=DEFAULT_MODEL):
        """Initialize Gemini API"""
        if api_key is None:
            load_dotenv()
            api_key = os.getenv('GEMINI_API_KEY')
        
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found. Set it in .env file or pass as parameter.")
        
        genai.configure(api_key=api_key)
        self.model_name = model_name
    
    def analyze_image(self, frame, user_query, system_prompt=None):
        """
        Analyze an image frame with Gemini
        
        Args:
            frame: cv2 VideoCapture frame (numpy array in BGR format)
            user_query: User's question/prompt about the image
            system_prompt: System instructions for the model (optional)
        
        Returns:
            Response from Gemini API
        """
        # Initialize model with system instruction if provided
        if system_prompt:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt
            )
        else:
            model = genai.GenerativeModel(self.model_name)
        
        # Convert cv2 frame (BGR) to PIL Image (RGB)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        
        # Generate content
        response = model.generate_content([user_query, img])
        return response


class CameraCapture:
    """Handles camera capture operations"""
    
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.cap = None
    
    def __enter__(self):
        """Context manager entry"""
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            raise RuntimeError(f"Error: Could not open camera {self.camera_index}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
    
    def capture_frame(self, rotate=False):
        """
        Capture a single frame
        
        Args:
            rotate: Whether to rotate frame 180 degrees
        
        Returns:
            Captured frame or None if failed
        """
        ret, frame = self.cap.read()
        if not ret:
            print("Failed to grab frame")
            return None
        
        if rotate:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        
        return frame
    
    def capture_interactive(self, window_title="Camera Feed"):
        """
        Capture frame with user interaction
        
        Args:
            window_title: Title for the display window
        
        Returns:
            Captured frame or None if cancelled
        """
        print(f"Camera started. Press 'c' to capture, 'q' to quit")
        
        while True:
            ret, frame = self.cap.read()
            
            if not ret:
                print("Failed to grab frame")
                return None
            
            # Display live feed
            cv2.imshow(f'{window_title} - Press "c" to capture, "q" to quit', frame)
            
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('c'):
                return frame.copy()
            elif key == ord('q'):
                print("Camera cancelled by user")
                return None


def process_gemini_response(response, extract_grid=True):
    """
    Process Gemini response and extract grid data
    
    Args:
        response: Gemini API response
        extract_grid: Whether to extract 'grid' key from JSON (default True)
    
    Returns:
        Grid data or full response text
    """
    try:
        text = response.text
        if extract_grid:
            data = json.loads(text)
            return data.get("grid")
        return text
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error parsing response: {e}")
        print(f"Raw response: {response.text}")
        return None


def save_debug_image(frame, filename):
    """Save frame for debugging purposes"""
    try:
        cv2.imwrite(filename, frame)
        print(f"Debug image saved: {filename}")
    except Exception as e:
        print(f"Failed to save debug image: {e}")


def run_camera_dobot(user_query, system_prompt=None, camera_index=2, 
                     save_debug=True, rotate_frame=True):
    """
    Capture image using Dobot-mounted camera and analyze with Gemini
    
    Args:
        user_query: User's question/prompt about the image
        system_prompt: System instructions for the model (optional)
        camera_index: Camera device index (default 2)
        save_debug: Whether to save captured frame for debugging
        rotate_frame: Whether to rotate frame 180 degrees
    
    Returns:
        Grid data from Gemini response or None if failed
    """
    try:
        # Move Dobot to camera position and capture
        with DobotController(port=PORT) as dobot:
            dobot.move_to_camera()
            
            with CameraCapture(camera_index) as camera:
                print("Camera started. Capturing frame...")
                frame = camera.capture_frame(rotate=rotate_frame)
        
        if frame is None:
            print("Frame capture failed")
            return None
        
        # Save debug images if requested
        if save_debug:
            save_debug_image(frame, "dobot_captured_frame.png")
        
        # Analyze with Gemini
        print("Sending frame to Gemini...")
        gemini = GeminiVisionAPI()
        response = gemini.analyze_image(frame, user_query, system_prompt)
        
        return process_gemini_response(response, extract_grid=True)
    
    except Exception as e:
        print(f"Error in run_camera_dobot: {e}")
        return None


def run_camera(user_query, system_prompt=None, camera_index=0, save_debug=True):
    """
    Interactive camera capture with user approval, then analyze with Gemini
    
    Args:
        user_query: User's question/prompt about the image
        system_prompt: System instructions for the model (optional)
        camera_index: Camera device index (default 0)
        save_debug: Whether to save captured frame for debugging
    
    Returns:
        Grid data from Gemini response or None if cancelled/failed
    """
    try:
        with CameraCapture(camera_index) as camera:
            frame = camera.capture_interactive()
        
        if frame is None:
            return None
        
        # Save debug image if requested
        if save_debug:
            save_debug_image(frame, "confirmed_frame.png")
        
        # Analyze with Gemini
        print("\nFrame captured! Sending to Gemini...")
        gemini = GeminiVisionAPI()
        response = gemini.analyze_image(frame, user_query, system_prompt)
        
        return process_gemini_response(response, extract_grid=True)
    
    except Exception as e:
        print(f"Error in run_camera: {e}")
        return None


# Example usage
if __name__ == "__main__":
    # System prompt
    SYSTEM_PROMPT = """You are a tic-tac-toe grid analyzer. Analyze the tic-tac-toe grid in the given image and respond based on the user's query."""
    
    # User query
    USER_QUERY = """Retrieve the 3x3 matrix from the image shown to you. Wherever there is a symbol seen simply place it in the same cell of the matrix you frame.
    Strictly return ONLY json with KEY as 'grid' and value as the matrix. Fill empty cells with empty strings (''). 
    Be cautious about the camera capture. It might also show the original image flipped.
    Remember one mistake can cost my life to play again. Additionally do not add ```json```. Only return the dict"""
    
    # Run camera with Dobot
    grid = run_camera_dobot(
        user_query=USER_QUERY,
        system_prompt=SYSTEM_PROMPT,
        camera_index=2
    )
    
    if grid:
        print("\n--- Extracted Grid ---")
        print(grid)
    else:
        print("No response - operation failed or was cancelled")