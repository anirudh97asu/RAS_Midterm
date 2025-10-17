import os, json, argparse, cv2, sys, time
from pathlib import Path
from src.mini_max_algo import TicTacToeAI, run_algorithm
from src.symbol_detection import run_camera, run_camera_dobot
from src.grid_module import build_grid
from src.draw_module import draw_module
from pydobot import Dobot

# ---------------- Configuration ----------------
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "config" / "grid_configuration.json"
PNG_PATH = SCRIPT_DIR / "input" / "3x3_grid_opencv.png"
OUTPUT_PATH = SCRIPT_DIR / "output"
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

# Dobot parameters
HOME_X, HOME_Y, HOME_Z, HOME_R = 232.09, -14.74, 129.59, 3.63
PEN_Z = -8.15
PORT = "/dev/ttyACM0"

# Game configuration
RECTANGLE_MAPPING = {
    (0, 0): 1, (0, 1): 2, (0, 2): 3,
    (1, 0): 4, (1, 1): 5, (1, 2): 6,
    (2, 0): 7, (2, 1): 8, (2, 2): 9,
}

WINNING_COMBINATIONS = {
    (1, 2, 3), (4, 5, 6), (7, 8, 9),  # Rows
    (1, 4, 7), (2, 5, 8), (3, 6, 9),  # Columns
    (1, 5, 9), (3, 5, 7)              # Diagonals
}

RECT_MAPPING_INV = {v: k for k, v in RECTANGLE_MAPPING.items()}

SYSTEM_PROMPT = """You are a tic-tac-toe grid analyzer. Analyze the tic-tac-toe grid in the given image and respond based on the user's query."""

GRID_QUERY = """Retrieve the 3x3 matrix from the image shown to you. Wherever there is a symbol seen simply place it in the same cell of the matrix you frame.
Strictly return ONLY json with KEY as 'grid' and value as the matrix. Fill empty cells with empty strings (''). Be cautious about the camera capture. It might also show the original image flipped.
Remember one mistake can cost my life to play again. Additionally do not add ``` json ```. Only return the dict"""


class GameState:
    """Manages game state and validation"""
    
    def __init__(self):
        self.cache = {}
    
    def find_rect(self, grid, symbol):
        """Find the rectangle where a new symbol was placed"""
        for i in range(len(grid)):
            for j in range(len(grid[i])):
                if grid[i][j].lower() == symbol.lower() and (i, j) not in self.cache:
                    rect = RECTANGLE_MAPPING[(i, j)]
                    self.cache[(i, j)] = symbol
                    return rect
        return None
    
    @staticmethod
    def all_cells_empty(grid):
        """Check if all cells in the grid are empty"""
        return all(cell == '' for row in grid for cell in row)
    
    @staticmethod
    def validate_symbol_insertion(rect_number, symbol, grid):
        """Validate that the correct symbol was placed in the correct cell"""
        pos_x, pos_y = RECT_MAPPING_INV[int(rect_number)]
        return grid[pos_x][pos_y].strip().lower() == symbol.lower()
    
    @staticmethod
    def validate_grid_count(grid, expected_count):
        """Validate that the grid has the expected number of symbols"""
        actual_count = sum(1 for row in grid for cell in row if cell != "")
        return actual_count == expected_count
    
    @staticmethod
    def check_winner(grid, human_symbol, robot_symbol):
        """Check if there's a winner"""
        human_positions = set()
        robot_positions = set()
        
        for i in range(3):
            for j in range(3):
                if grid[i][j] == human_symbol:
                    human_positions.add(RECTANGLE_MAPPING[(i, j)])
                elif grid[i][j] == robot_symbol:
                    robot_positions.add(RECTANGLE_MAPPING[(i, j)])
        
        # Need at least 3 symbols to win
        human_win = len(human_positions) >= 3 and any(
            combo.issubset(human_positions) for combo in WINNING_COMBINATIONS
        )
        robot_win = len(robot_positions) >= 3 and any(
            combo.issubset(robot_positions) for combo in WINNING_COMBINATIONS
        )
        
        return human_win, robot_win


def get_player_input(prompt, valid_options, max_retries=2):
    """Get validated input from the player"""
    for attempt in range(max_retries):
        user_input = input(prompt).strip().lower()
        if user_input in valid_options:
            return user_input
        print(f"Invalid input. Please enter one of: {', '.join(valid_options)}")
    return None


def initialize_game():
    """Initialize game settings and player configuration"""
    print("------------ Let's start Tic Tac Toe Game ------------")
    
    # Get human symbol
    human_symbol = get_player_input(
        "Enter which symbol you would like (x/o): ",
        ["x", "o"]
    )
    
    if human_symbol is None:
        print("Invalid symbol selection. Exiting.")
        sys.exit(1)
    
    robot_symbol = "o" if human_symbol == "x" else "x"
    print(f"Human: {human_symbol.upper()}, Robot: {robot_symbol.upper()}")
    
    # Get starting player
    player_choice = get_player_input(
        "Who plays first? (1=Robot, 2=Human): ",
        ["1", "2"]
    )
    
    if player_choice is None:
        print("Invalid choice. Robot will start by default.")
        player_choice = "1"
    
    player_info = {
        "1": "robot",
        "2": "human"
    }
    
    starting_player = player_choice
    
    return human_symbol, robot_symbol, starting_player, player_info


def process_human_turn(game_state, grid, human_symbol, simulation_count, use_camera_func):
    """Process a human player's turn"""
    print("\n--- Human's Turn ---")
    time.sleep(2)
    
    grid_run = use_camera_func(user_query=GRID_QUERY, system_prompt=SYSTEM_PROMPT)
    
    if grid_run is None:
        print("Failed to capture grid.")
        return None, False
    
    rect = game_state.find_rect(grid_run, human_symbol)
    
    if rect is None:
        print("Error: Symbol must be placed in an empty cell.")
        return None, False
    
    if not game_state.validate_grid_count(grid_run, simulation_count):
        print("Error: Only one symbol can be placed per turn.")
        return None, False
    
    if not game_state.validate_symbol_insertion(rect, human_symbol, grid_run):
        print("Error: Invalid symbol placement.")
        return None, False
    
    print(f"✓ Human placed {human_symbol.upper()} at position {rect}")
    return grid_run, True


def process_robot_turn(game_state, grid, robot_symbol, simulation_count, use_camera_func, draw_mod=None):
    """Process the robot's turn"""
    print("\n--- Robot's Turn ---")
    
    rectangle = run_algorithm(board=grid)
    print(f"Robot placing {robot_symbol.upper()} at position {rectangle}")
    
    if draw_mod:
        ret = draw_mod.draw(rectangle_number=int(rectangle), dobot_symbol=robot_symbol)
        if not ret:
            print("Error: Failed to draw symbol.")
            return None, False
        time.sleep(3.0)  # Wait for Dobot to disconnect
    else:
        # Test mode
        print(f"[TEST MODE] Draw {robot_symbol.upper()} at position {rectangle}, then press 'y':")
        if input().strip().lower() != 'y':
            return None, False
    
    grid_run = use_camera_func(user_query=GRID_QUERY, system_prompt=SYSTEM_PROMPT)
    
    if grid_run is None:
        print("Failed to capture grid.")
        return None, False
    
    if not game_state.validate_grid_count(grid_run, simulation_count):
        print("Error: Grid count mismatch.")
        return None, False
    
    if not game_state.validate_symbol_insertion(rectangle, robot_symbol, grid_run):
        print("Error: Symbol not placed correctly.")
        return None, False
    
    print(f"✓ Robot placed {robot_symbol.upper()} at position {rectangle}")
    return grid_run, True


def run_game_loop(human_symbol, robot_symbol, starting_player, player_info, use_camera_func, draw_mod=None):
    """Main game loop"""
    game_state = GameState()
    
    # Initialize grid
    print("\nInitializing grid...")
    if draw_mod:  # Dobot mode
        grid = [['', '', ''], ['', '', '']]
        check = True
    else:  # Test mode
        init_query = "Initialize an empty 3x3 matrix with empty strings (''). Return ONLY json with KEY 'grid'. Do not add ```json```."
        grid = use_camera_func(user_query=init_query, system_prompt=SYSTEM_PROMPT)
        check = game_state.all_cells_empty(grid)
    
    if not check:
        print("Error: Grid cells are not empty. Please clear the board.")
        return
    
    print("✓ Grid is ready. Starting game...\n")
    
    simulation_count = 0
    current_player = starting_player
    
    while simulation_count < 9:
        simulation_count += 1
        print(f"\n{'='*50}")
        print(f"Turn {simulation_count}/9")
        print(f"{'='*50}")
        
        # Check for winner (starting from turn 3)
        if simulation_count >= 3:
            human_win, robot_win = game_state.check_winner(grid, human_symbol, robot_symbol)
            if human_win or robot_win:
                winner = "Human" if human_win else "Robot"
                print(f"\n🎉 {winner} wins!")
                return
        
        # Process turn
        if player_info[current_player] == "human":
            grid, success = process_human_turn(game_state, grid, human_symbol, simulation_count, use_camera_func)
        else:
            grid, success = process_robot_turn(game_state, grid, robot_symbol, simulation_count, use_camera_func, draw_mod)
        
        if not success or grid is None:
            print("Game ended due to error.")
            sys.exit(1)
        
        # Switch player
        current_player = "2" if current_player == "1" else "1"
    
    print("\n🤝 Game ended in a draw!")


def run_simulation_dobot():
    """Run game with physical Dobot"""
    build_grid()  # Build the physical grid
    
    human_symbol, robot_symbol, starting_player, player_info = initialize_game()
    
    # Initialize draw module
    dm = draw_module(
        port=PORT,
        config_path=CONFIG_PATH,
        HOME_X=HOME_X, HOME_Y=HOME_Y, HOME_Z=HOME_Z, HOME_R=HOME_R,
        z_draw=PEN_Z,
        z_lift=20.0,
        inset=2.0,
        symbol_margin=1.5
    )
    
    camera_func = lambda **kwargs: run_camera_dobot(**kwargs, camera_index=2)
    run_game_loop(human_symbol, robot_symbol, starting_player, player_info, camera_func, dm)


def run_simulation_test():
    """Run game in test mode (manual drawing)"""
    human_symbol, robot_symbol, starting_player, player_info = initialize_game()
    run_game_loop(human_symbol, robot_symbol, starting_player, player_info, run_camera)


if __name__ == "__main__":
    # run_simulation_test()
    run_simulation_dobot()