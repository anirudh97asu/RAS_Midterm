import google.generativeai as genai
from PIL import Image
import cv2
import os
import sys
from pydobot import Dobot
from dotenv import load_dotenv
from pathlib import Path
import time

# Add src directory to path
src_path = Path(__file__).parent
sys.path.insert(0, str(src_path))
import json

# dobot parameters
HOME_X = 232.09
HOME_Y = -14.74
HOME_Z = 129.59
HOME_R = 3.63

PEN_Z = -5.15


CAMERA_X = 210.93
CAMERA_Y = 20.34
CAMERA_Z = 0
CAMERA_R = 6.49

port = "/dev/ttyACM0"  # identify and fix_port


def send_image_to_gemini(frame, user_query, system_prompt=None):
    """
    Send a cv2 frame and text prompt to Gemini API using the official client
    
    Args:
        frame: cv2 VideoCapture frame (numpy array)
        user_query: User's question/prompt about the image
        system_prompt: System instructions for the model (optional)
    
    Returns:
        Response from Gemini API
    """
    
    # Load API key from .env file
    load_dotenv()
    api_key = os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in .env file")
    
    # Configure the API key
    genai.configure(api_key=api_key)
    
    # Initialize the model with system instruction if provided
    if system_prompt:
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            system_instruction=system_prompt
        )
    else:
        model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Convert cv2 frame (BGR) to PIL Image (RGB)
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(frame_rgb)
    
    # Generate content with user query and image
    response = model.generate_content([user_query, img])
    
    return response


def run_camera_dobot(user_query, system_prompt=None, camera_index=2):
    """
    Run camera feed without user approval before sending to Gemini
    
    Args:
        user_query: User's question/prompt about the image
        system_prompt: System instructions for the model (optional)
        camera_index: Camera device index (default 0 for webcam)
    
    Returns:
        Response from Gemini API or None if cancelled
    """
    
    # Move Dobot Camera Position
    dobot = Dobot(port=port)
    dobot.move_to(CAMERA_X, CAMERA_Y, CAMERA_Z, CAMERA_R)

    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print("Error: Cound not open camera")
        return None
    
    print("Camera Started and Capturing Frames")

    #captured_frame = None
    ret, frame= cap.read()
    #frame = flipped_image = cv2.flip(frame, -1)
    #frame  = cv2.rotate(frame, cv2.ROTATE_180)

    cap.release()
    cv2.destroyAllWindows()

    dobot.move_to(HOME_X, HOME_Y, HOME_Z, HOME_R)
    dobot.close()

    if not ret:
        print("Failed to grab frame")
        sys.exit(0)

    if frame is not None:
        #cv2.imwrite(r"dobot_captured_frame.png", frame)
        cv2.imwrite(r"dobot_captured_frame_rotated.png", cv2.rotate(frame, cv2.ROTATE_180))

        rotated_frame = cv2.rotate(frame, cv2.ROTATE_180) 
        # Send to Gemini
        response = send_image_to_gemini(
            frame=rotated_frame,
            #frame=cv2.rotate(captured_frame, cv2.ROTATE_180),
            user_query=user_query,
            system_prompt=system_prompt
        )

        text = response.text
        info = json.loads(text)
        return info["grid"]

    return None



def run_camera(user_query, system_prompt=None, camera_index=0):
    """
    Run camera feed with user approval before sending to Gemini
    
    Args:
        user_query: User's question/prompt about the image
        system_prompt: System instructions for the model (optional)
        camera_index: Camera device index (default 0 for webcam)
    
    Returns:
        Response from Gemini API or None if cancelled
    """
    
    # Open video capture
    cap = cv2.VideoCapture(camera_index)
    
    if not cap.isOpened():
        print("Error: Could not open camera")
        return None
    
    print("Camera started. Press 'c' to capture, 'q' to quit")
    
    captured_frame = None
    
    # Live camera feed loop
    while True:
        ret, frame = cap.read()
        
        if not ret:
            print("Failed to grab frame")
            break
        
        # Display the live feed
        cv2.imshow('Camera Feed - Press "c" to capture, "q" to quit', frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        # Capture frame with 'c' key
        if key == ord('c'):
            captured_frame = frame.copy()
            break
        # Quit with 'q' key
        elif key == ord('q'):
            print("Camera cancelled by user")
            cap.release()
            cv2.destroyAllWindows()
            return None
    
    cap.release()
    cv2.destroyAllWindows()
    
    # Send captured frame to Gemini
    if captured_frame is not None:
        cv2.imwrite(r"confirmed_frame.png", captured_frame)
        print("\nFrame captured! Sending to Gemini...")
        
        # Send to Gemini
        response = send_image_to_gemini(
            frame=captured_frame,
            #frame=cv2.rotate(captured_frame, cv2.ROTATE_180),
            user_query=user_query,
            system_prompt=system_prompt
        )

        text = response.text
        info = json.loads(text)
        return info["grid"]
    
    return None


# Example usage
if __name__ == "__main__":
    # System prompt (instructions for the model)
    SYSTEM_PROMPT = """You are a tic-tac-toe grid analyzer. Analyze the tic-tac-toe grid in the given image and respond based on the user's query."""
    
    # User query about the image
    USER_QUERY = "Retrieve the 3x3 matrix from the image shown to you. Wherever there is a symbol seen simply place it in the same cell of the matrix you frame.\
                        Strictly return ONLY json with KEY as 'grid' and value as the matrix. Fill empty cells with empty strings (''). Be cautious about the camera capture. It might also show the original image flipped.\
                        Remember one maistake can cost my life to play again. Additionally do not add ``` json ```. Only return the dict"
    
    # Run camera with approval flow
    response = run_camera_dobot(
        user_query=USER_QUERY,
        system_prompt=SYSTEM_PROMPT,
        camera_index=2  # 0 for default webcam
    )
    
    if response:
        # Print the response text
        print("\n--- Gemini's Response ---")
        print(response)
        # Optional: Access more details
        # print("\n--- Additional Details ---")
        # print(f"Finish Reason: {response.candidates[0].finish_reason}")

    else:
        print("No response - operation was cancelled")