from serial.tools import list_ports
from pydobot import Dobot
import time
import os

def find_dobot_ports():
    """Find potential Dobot ports by looking for USB devices"""
    ports = list(list_ports.comports())
    
    print("=== ALL DETECTED PORTS ===")
    for i, p in enumerate(ports):
        print(f"{i}: {p.device} - {p.description} - {p.manufacturer}")
    
    print("\n=== FILTERING FOR POTENTIAL DOBOT PORTS ===")
    potential_ports = []
    
    for p in ports:
        # Look for USB ports or ports with relevant keywords
        if any(keyword in str(p.description).lower() for keyword in ['usb', 'serial', 'ch340', 'ch341', 'ftdi', 'cp210']):
            potential_ports.append(p)
            print(f"✓ Potential Dobot: {p.device} - {p.description}")
        elif 'ttyUSB' in p.device or 'ttyACM' in p.device:
            potential_ports.append(p)
            print(f"✓ USB Serial: {p.device} - {p.description}")
        else:
            print(f"✗ Unlikely: {p.device} - {p.description}")
    
    return potential_ports

def test_dobot_connection(port_device):
    """Test connection to a specific port"""
    print(f"\n=== TESTING CONNECTION TO {port_device} ===")
    
    # First check if the port file exists
    if not os.path.exists(port_device):
        print(f"❌ Port file {port_device} does not exist!")
        return False
    
    # Check permissions
    try:
        if not os.access(port_device, os.R_OK | os.W_OK):
            print(f"❌ No read/write permissions for {port_device}")
            print("Try: sudo chmod 666 {port_device}")
            print("Or add user to dialout group: sudo usermod -a -G dialout $USER")
            return False
    except Exception as e:
        print(f"❌ Permission check failed: {e}")
        return False
    
    # Try to connect to Dobot
    device = None
    try:
        print(f"Attempting to connect to {port_device}...")
        device = Dobot(port=port_device)
        print("✓ Dobot connected successfully!")
        
        # Try to get pose to verify it's working
        pose, joints = device.get_pose()
        print(f"✓ Current pose: {pose}")
        print(f"✓ Current joints: {joints}")
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False
    
    finally:
        if device:
            device.close()
            print("Connection closed.")

def main():
    print("=== DOBOT CONNECTION DIAGNOSTIC ===\n")
    
    # Find potential Dobot ports
    potential_ports = find_dobot_ports()
    
    if not potential_ports:
        print("\n❌ No potential Dobot ports found!")
        print("\nTroubleshooting steps:")
        print("1. Make sure Dobot is connected via USB")
        print("2. Check if USB cable is working (try different cable)")
        print("3. Try different USB ports")
        print("4. Check if Dobot is powered on")
        return
    
    print(f"\nFound {len(potential_ports)} potential port(s)")
    
    # Test each potential port
    success = False
    for port in potential_ports:
        if test_dobot_connection(port.device):
            print(f"\n🎉 SUCCESS! Dobot found on {port.device}")
            success = True
            break
    
    if not success:
        print("\n❌ Could not connect to Dobot on any port")
        print("\nAdditional troubleshooting:")
        print("1. Check USB cable connection")
        print("2. Try: sudo chmod 666 /dev/ttyUSB* /dev/ttyACM*")
        print("3. Add user to dialout group: sudo usermod -a -G dialout $USER")
        print("4. Restart computer after adding to dialout group")
        print("5. Try different baud rates (115200, 9600, 57600)")

if __name__ == "__main__":
    main()
 