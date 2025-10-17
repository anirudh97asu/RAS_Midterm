# main_tictactoe.py
import os, json, argparse, cv2
from src.mini_max_algo import TicTacToeAI, run_algorithm
from src.symbol_detection import run_camera, run_camera_dobot
from src.grid_module import build_grid
from src.draw_module import draw_module
#from src.opencv_draw import DrawModuleCV
from pydobot import Dobot
from pathlib import Path
import sys
import time

# ---------------- Paths (Pathlib) ----------------
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = (SCRIPT_DIR / "config" / "grid_configuration.json")
PNG_PATH = (SCRIPT_DIR / "input" / "3x3_grid_opencv.png")
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)  # ensure ../config exists
OUTPUT_PATH = SCRIPT_DIR / "output" 


# dobot parameters
HOME_X = 232.09
HOME_Y = -14.74
HOME_Z = 129.59
HOME_R = 3.63

PEN_Z = -8.15


port = "/dev/ttyACM0"

rectangle_mapping = {(0, 0): 1, 
                     (0, 1): 2, 
                     (0, 2): 3,
                     (1,0): 4,
                     (1,1): 5,
                     (1,2): 6,
                     (2,0): 7,
                     (2,1): 8,
                     (2,2): 9,
    }

winning_table = {(1,2,3): 1 ,
                 (4,5,6): 1,
                 (7,8,9): 1,
                 (1,4,7): 1,
                 (2,5,8): 1,
                 (3,6,9): 1,
                 (1,5,9): 1,
                 (3,5,7): 1}

cache = {}

rect_mapping_inv = {v:k for k,v in rectangle_mapping.items()}


SYSTEM_PROMPT = """You are a tic-tac-toe grid analyzer. Analyze the tic-tac-toe grid in the given image and respond based on the user's query."""

def find_rect(grid, symbol):
    rect = None
    for i in range(len(grid)):
        for j in range(len(grid)):

            if grid[i][j].lower() == symbol.lower() and cache.get((i,j)) is None:
                rect = rectangle_mapping[(i, j)]
                cache[(i,j)] = symbol
    return rect


def all_cells_empty(grid, empty=''):
    return all(cell == empty for row in grid for cell in row)


def validate_symbol_insertion(rect_number, symbol, grid):
    
    check = False

    pos_x, pos_y = rect_mapping_inv[int(rect_number)]

    if grid[pos_x][pos_y].strip().lower() == symbol.lower():
        check = True
    
    return check


def validate_grid_count(grid, iteration_count):
    
    check=False
    grid_count = 0
    for i in range(len(grid)):
        for j in range(len(grid)):
            if grid[i][j] != "":
                grid_count += 1
    
    if iteration_count == grid_count:
        check = True

    return check


def check_win_or_not(grid, human_symbol, robot_symbol):

    human_win = False
    robot_win = False

    grid_size = 3
    
    human_symbol_records = []
    robot_symbol_records = []

    for i in range(grid_size):
        for j in range(grid_size):
            
            if grid[i][j] == human_symbol:
                rectangle_pos = rect_mapping_inv[(i, j)]
                human_symbol_records.append(rectangle_pos)
            elif grid[i][j] == robot_symbol:
                rectangle_pos = rect_mapping_inv[(i, j)]
                robot_symbol_records.append(rectangle_pos)
    
    if len(robot_symbol_records) < 3 and len(human_symbol_records) < 3:

        return human_win, robot_win
    
    elif len(robot_symbol_records) > 2:
        robot_win = bool(winning_table[tuple(robot_symbol_records)])
        return human_win, robot_win
    
    elif len(human_symbol_records) > 2:
        human_win = bool(winning_table[tuple(human_symbol_records)])
        return human_win, robot_win
        
    else:
        robot_win = bool(winning_table[tuple(robot_symbol_records)])
        human_win = bool(winning_table[tuple(human_symbol_records)])
        return human_win, robot_win


def run_simulation_dobot():

    # player_sim_1 = None
    # player_sim_2 = None
    player_info = {}

    solver = build_grid()

    print(f"Grid has been built successfully using solver {solver}")

    with open(CONFIG_PATH, "r") as f:

        config = json.load(f)

    #CX, CY, CZ, CR = config["cell_rectangle_1"][0][0], config["cell_rectangle_1"][1][1], 15, 0

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


    max_retry = 0
    print("------------Let's start Tic Tac Toe Game")
    print("Enter which input symbol you would love to take")
    human_symbol = None 
    user_input = input()
    
    if user_input.lower() in ["x", "o"]:
        human_symbol = user_input
        print("Human Symbol Processed Successfully")
    
    
    else:
        print("You have entered the wrong symbol. It can only be either 'x' or an 'o'. Please Enter again")
        max_retry += 1
        user_input =  input()
        if user_input.lower() in ["x", "o"]:
            human_symbol = user_input
            print("Human Symbol Processed Successfully")
        
        
    
    if max_retry >= 1 and human_symbol is None:
        print("user_input cannot be None. Please re-run the script.")
        sys.exit(0)

    robot_symbol = None
    
    if human_symbol == "o":
        robot_symbol = "x"
    
    else:
        robot_symbol = "o"
    
    if human_symbol is not None:
        print("Enter who can play first: 1 -----> me and 2 ------> you")
        starting_player = None
        player_input = input()
        
        if player_input not in ["1", "2"]:
            print("Incorrect value is given. I will assume I will start playing the game.")
            starting_player = "1"
            player_info[starting_player] = "dobot"
            player_info["2"] = "human"

        elif player_input == "1":
            starting_player = "1"
            player_info[player_input] = "dobot"
            player_info["2"] = "human"
        
        else:
            starting_player = "2"
            player_info[starting_player] = "human"
            player_info["1"] = "dobot"
        
        # if starting_player is None:
        #     sys.exit(0)


        print("Starting the game.")
        
        # print("Initializing the grid.....")
        # dobot_ins = Dobot(port=port)
        # print(f"✓ Real Dobot connected on port: {port}")
        # dobot_ins.move_to(CAMERA_X,CAMERA_Y,CAMERA_Z,CAMERA_R)
        # dobot_ins.close()
        #grid = run_camera_dobot(user_query="Initialize an empty 3x3 matrix with an empty string -> ''. Strictly return ONLY json with KEY as 'grid' and value as the matrix. \
        #          Additionally do not add ``` json ```. Only return the dict", system_prompt=SYSTEM_PROMPT, camera_index=2)

        # print("CHecking if all the cells are empty are not.")
        # check = all_cells_empty(grid)
        grid = [['', '', ''], ['', '', ''], ['', '', '']]
        check=True

        if check:
            
            print("Grid Cells are empty. Go ahead with the game")

            # --- load + draw ---
            # dm = draw_module(port=port, config_path=CONFIG_PATH, HOME_X=HOME_X, HOME_Y=HOME_Y, HOME_Z=HOME_Z, HOME_R=HOME_R, z_draw=PEN_Z,
            # z_lift=20.0,     # clearance above z_draw for moves
            # inset=2.0,       # stay inside the box a bit
            # symbol_margin=1.5 )
            
            simulation_count = 0
            flag = None
            human_win, robot_win = False, False
            player = starting_player
            grid_sim = grid
            winner = None

            print("robot_symbol", robot_symbol)

            while simulation_count < 9:

                simulation_count += 1

                if grid_sim is None:
                    break

                if simulation_count >= 3:
                    human_win, robot_win = check_win_or_not(grid_sim, human_symbol, robot_symbol)

                    if human_win:
                        winner="human"
                        break
                    if robot_win:
                        winner="robot"
                        break

                if player == "2":

                    print(f"{player_info.get(player)} Turn to draw the symbol")
                    
                    print(time.sleep(5))
                        
                    grid_run = run_camera_dobot(user_query="Retrieve the 3x3 matrix from the image shown to you. Wherever there is a symbol seen simply place it in the same cell of the matrix you frame.\
                    Strictly return ONLY json with KEY as 'grid' and value as the matrix. Fill empty cells with empty strings (''). Be cautious about the camera capture. It might also show the original image flipped.\
                    Remember one maistake can cost my life to play again. Additionally do not add ``` json ```. Only return the dict", system_prompt=SYSTEM_PROMPT, camera_index=2)
                    
                    print("grid_run", grid_run)
                    rect = find_rect(grid_run, symbol=human_symbol)
                    
                    if rect is None:
                        print("You should insert the symbol at the desired square position. It's invalid if it's inserted elsewhere")
                        break
                    
                    print("grid_run", grid_run)
                    check_count = validate_grid_count(grid_run, simulation_count)

                    if not check_count:
                        print("You cannot insert multiple symbols in multiple places. Only one symbol insertion is allowed in one iteration.")
                        break
                    
                    check = validate_symbol_insertion(rect, symbol=human_symbol, grid=grid_run)
                    check_dobot_symbol = validate_symbol_insertion(rect, symbol=robot_symbol, grid=grid_run)
                    
                    if check:
                        print("Success", grid_run)
                        grid_sim = grid_run
                    
                    elif check_dobot_symbol:
                        print("You have inserted the wrong symbol in the place where human symbol should be present.")
                        sys.exit(0)
                    
                    else:
                        print("There is some problem in symbol insertion at the corresponding cell")
                        grid_sim = None
                        break

                    player = "1"

                
                elif player == "1":
                            
                    grid_run = None

                    print(f"{player_info.get(player)} Turn to draw the symbol. Enter 'y' once the symbol is drawn from your end.")
                    
                    rectangle = run_algorithm(board=grid_sim)
                    print("rect",rectangle)

                    
                    ret = dm.draw(rectangle_number=int(rectangle), dobot_symbol=robot_symbol)
                    print("Waiting for Dobot to fully disconnect before camera capture...")
                    time.sleep(3.0)  # 
                    
                    if ret:
                        
                        grid_run = run_camera_dobot(user_query="Retrieve the 3x3 matrix from the image shown to you. Wherever there is a symbol seen simply place it in the same cell of the matrix your frame.\
                            Strictly return ONLY json with KEY as 'grid' and value as the matrix. Fill empty cells with empty strings (''). Be cautious about the camera capture. It might also show the original image flipped.\
                            Remember one maistake can cost my life to play again. Additionally do not add ``` json ```. Only return the dict", system_prompt=SYSTEM_PROMPT, camera_index=2)
                        
                    check_count = validate_grid_count(grid_run, simulation_count)

                    if not check_count:
                        
                        print("You cannot insert multiple symbols in multiple places. Only one symbol insertion is allowed in one iteration.")
                        break
                        
                    
                    check = validate_symbol_insertion(rectangle, symbol=robot_symbol, grid=grid_run)
                    
                    if check:
                        grid_sim = grid_run
                    
                    else:
                        print("There is some problem in symbol insertion at the corresponding cell")
                        grid_sim = None
                        break
                    
                    player = "2"
                            
                
            if grid_sim is None:
                print("Grid Simulation cannot be None. There is an error in your code.")
                sys.exit(0)

            if human_win:
                print(f"Human has won this game. Human_symbol: {human_symbol}")
            
            elif robot_win:
                print(f"Robot has won this game. Robot_Symbol: {robot_symbol}")

            elif not human_win and not robot_win:
                print("The match is draw.")
                sys.exit(0)
            
            else:
                sys.exit(0)


def run_simulation_test():

    #solver = build_grid()

    
    player_info = {}
    #print(f"Grid has been built successfully using solver {solver}")


    max_retry = 0
    print("------------Let's start Tic Tac Toe Game")
    print("Enter which input symbol you would love to take")
    human_symbol = None
    user_input = input()
    
    if user_input.lower() in ["x", "o"]:
        human_symbol = user_input
        print("Human Symbol Processed Successfully")
    
    
    else:
        print("You have entered the wrong symbol. It can only be either 'x' or an 'o'. Please Enter again")
        max_retry += 1
        user_input =  input()
        if user_input.lower() in ["x", "o"]:
            human_symbol = user_input
            print("Human Symbol Processed Successfully")
        
        
    
    if max_retry >= 1 and human_symbol is None:
        print("user_input cannot be None. Please re-run the script.")
        sys.exit(0)

    robot_symbol = None
    if human_symbol == "o":
        robot_symbol = "x"
    
    else:
        robot_symbol = "o"


    
    if human_symbol is not None:
        print("Enter who can play first: 1 -----> me and 2 ------> you")
        starting_player = None
        player_input = input()
        
        if player_input not in ["1", "2"]:
            print("Incorrect value is given. I will assume I will start playing the game.")
            starting_player = "1"
            player_info[starting_player] = "dobot"
            player_info["2"] = "human"

        elif player_input == "1":
            starting_player = "1"
            player_info[player_input] = "dobot"
            player_info["2"] = "human"
        
        else:
            starting_player = "2"
            player_info[starting_player] = "human"
            player_info["1"] = "dobot"
        
        # if starting_player is None:
        #     sys.exit(0)


        print("Starting the game.")

        
        print("Initializing the grid.....")
        grid = run_camera(user_query="Initialize an empty 3x3 matrix with an empty string -> ''. Strictly return ONLY json with KEY as 'grid' and value as the matrix. \
                  Additionally do not add ``` json ```. Only return the dict", system_prompt=SYSTEM_PROMPT)

        print("CHecking if all the cells are empty are not.")
        print("grid", grid)
        check = all_cells_empty(grid)
        print(check)

        if check:
            
            print("Grid Cells are empty. Go ahead with the game")

            # --- load + draw ---
            #dm = draw_module(port=port, config_path=CONFIG_PATH, HOME_X=HOME_X, HOME_Y=HOME_Y, HOME_Z=HOME_Z, HOME_R=HOME_R)
            
            simulation_count = 0
            flag = None
            human_win, robot_win = False, False
            player = starting_player
            grid_sim = grid
            winner = None

            while simulation_count < 9:

                simulation_count += 1

                print("Simulation_Count", simulation_count)

                if grid_sim is None:
                    break

                if simulation_count >= 3:
                    human_win, robot_win = check_win_or_not(grid_sim, human_symbol, robot_symbol)

                    if human_win:
                        winner="human"
                        break
                    if robot_win:
                        winner="robot"
                        break

                if player == "2":
                    
                    print(f"{player} simulation running")
                    print(f"{player_info.get(player)} Turn to draw the symbol. Enter 'y' once the symbol is drawn from your end.")

                    ck = input()
                    
                    if ck == "y":
                        
                        grid_run = run_camera(user_query="Retrieve the 3x3 matrix from the image shown to you. Wherever there is a symbol seen simply place it in the same cell of the matrix your frame.\
                        Strictly return ONLY json with KEY as 'grid' and value as the matrix. Fill empty cells with empty strings ('').  Be cautious about the camera capture. It might also show the original image flipped.\
                        Remember one maistake can cost my life to play again. Additionally do not add ``` json ```. Only return the dict", system_prompt=SYSTEM_PROMPT)

                        print("[DEBUG]: ", simulation_count, grid_run)

                        rect = find_rect(grid_run, symbol=human_symbol)
                        print(rect, rect is None)
                        
                        if rect is None:
                            print("You should insert the symbol at the desired square position. It's invalid if it's inserted elsewhere")
                            break
                        
                        check_count = validate_grid_count(grid_run, simulation_count)

                        if not check_count:
                            print("You cannot insert multiple symbols in multiple places. Only one symbol insertion is allowed in one iteration.")
                            break
                        
                        check = validate_symbol_insertion(rect, symbol=human_symbol, grid=grid_run)
                        
                        if check:
                            grid_sim = grid_run
                            print("SUccess", grid_sim)

                        else:
                            print("There is some problem in symbol insertion at the corresponding cell")
                            grid_sim = None
                        
                        player = "1"
                
                elif player == "1":
                    
                    print(f"{player} simulation running")
                    print(f"{player_info.get(player)} Turn to draw the symbol. Enter 'y' once the symbol is drawn from your end.")
                    
                    rectangle = run_algorithm(board=grid_sim)
                    print(f"Draw symbol {robot_symbol} at square position: {rectangle} and enter 'y' once done.")
                    
                    dk = input()
                    
                    if dk == "y":
                        
                        grid_run = run_camera(user_query="Retrieve the 3x3 matrix from the image shown to you. Wherever there is a symbol seen simply place it in the same cell of the matrix your frame.\
                        Strictly return ONLY json with KEY as 'grid' and value as the matrix.Fill empty cells with empty strings (''). Be cautious about the camera capture. It might also show the original image flipped.\
                        Remember one maistake can cost my life to play again. Additionally do not add ``` json ```. Only return the dict", system_prompt=SYSTEM_PROMPT)

                        print("[DEBUG]: ", simulation_count, grid_run)

                        rect = find_rect(grid_run, symbol=robot_symbol)

                        if rect != rectangle:
                            print(f"Rectangle is not inserted at {rectangle} position. Game is over")
                            break

                        check_count = validate_grid_count(grid_run, simulation_count)

                        if not check_count:
                        
                            print("You cannot insert multiple symbols in multiple places. Only one symbol insertion is allowed in one iteration.")
                            break
                        
                        check = validate_symbol_insertion(rectangle, symbol=robot_symbol, grid=grid_run)
                        
                        if check:
                            grid_sim = grid_run
                    
                        else:
                            print("There is some problem in symbol insertion at the corresponding cell")
                            grid_sim = None   

                        player = "2"   

                    else:
                        print("Invalid input. Breaking")
                        sys.exit(0)

                

            if grid_sim is None:
                print("Grid Simulation cannot be None. There is an error in your code.")
                sys.exit(0)

            if human_win:
                print(f"Human has won this game. Human_symbol: {human_symbol}")
            
            elif robot_win:
                print(f"Robot has won this game. Robot_Symbol: {robot_symbol}")

            elif not human_win and not robot_win:
                print("The match is draw.")
                sys.exit(0)
            
            else:
                sys.exit(0)

if __name__ == "__main__":

    #run_simulation_test()
    run_simulation_dobot()

