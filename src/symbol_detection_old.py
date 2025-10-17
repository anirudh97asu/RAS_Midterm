import google.generativeai as genai
from PIL import Image
import cv2
import os
from dotenv import load_dotenv

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
        cv2.imshow('Camera Feed', frame)
        cv2.destroyAllWindows()
        cap.release()
        captured_frame = frame.copy()
        
        #key = cv2.waitKey(1) & 0xFF
        
        # Capture frame with 'c' key
        #if key == ord('c'):
        #    break
        # Quit with 'q' key
        # elif key == ord('q'):
        #     print("Camera cancelled by user")
        #     cap.release()
        #     cv2.destroyAllWindows()
        #     return None
    
    # cap.release()
    # cv2.destroyAllWindows()
    
    # Send captured frame to Gemini
    if captured_frame is not None:
        print("\nFrame captured! Sending to Gemini...")
        
        # Send to Gemini
        response = send_image_to_gemini(
            frame=captured_frame,
            user_query=user_query,
            system_prompt=system_prompt
        )
        
        return response
    
    return None


# Example usage
if __name__ == "__main__":
    # System prompt (instructions for the model)
    SYSTEM_PROMPT = """You are a tic-tac-toe grid analyzer. Analyze the tic-tac-toe grid in the given image and respond based on the user's query."""
    
    # User query about the image
    USER_QUERY = "What's in this image?"
    
    # Run camera with approval flow
    response = run_camera(
        user_query=USER_QUERY,
        system_prompt=SYSTEM_PROMPT,
        camera_index=0  # 0 for default webcam
    )
    
    if response:
        # Print the response text
        print("\n--- Gemini's Response ---")
        print(response.text)
        
        # Optional: Access more details
        print("\n--- Additional Details ---")
        print(f"Finish Reason: {response.candidates[0].finish_reason}")
    else:
        print("No response - operation was cancelled")