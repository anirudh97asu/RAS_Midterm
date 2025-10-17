from pathlib import Path
import cv2

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


# ---------------- Paths (Pathlib) ----------------
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = (SCRIPT_DIR.parent / "config" / "grid_configuration.json")
PNG_PATH = (SCRIPT_DIR / "input" / "3x3_grid_opencv.png")
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)  # ensure ../config exists

class TicTacToeAI:
    def __init__(self, ai_symbol='O', human_symbol='X'):
        self.ai = ai_symbol
        self.human = human_symbol
    
    def get_best_move(self, board):
        """Returns best move (row, col) for AI given current board state"""
        best_score = float('-inf')
        best_move = None
        
        for i in range(3):
            for j in range(3):
                if board[i][j] == '':
                    board[i][j] = self.ai
                    score = self.minimax(board, 0, False)
                    board[i][j] = ''
                    
                    if score > best_score:
                        best_score = score
                        best_move = (i, j)
        
        return best_move
    
    def minimax(self, board, depth, is_maximizing):
        """Recursive minimax algorithm with depth awareness"""
        result = self.check_winner(board)
        
        # Return score based on depth - prioritize faster wins and slower losses
        if result == self.ai:
            return 10 - depth  # Win sooner is better
        elif result == self.human:
            return depth - 10  # Lose later is better (blocking)
        elif self.is_full(board):
            return 0
        
        if is_maximizing:
            best_score = float('-inf')
            for i in range(3):
                for j in range(3):
                    if board[i][j] == '':
                        board[i][j] = self.ai
                        score = self.minimax(board, depth + 1, False)
                        board[i][j] = ''
                        best_score = max(score, best_score)
            return best_score
        else:
            best_score = float('inf')
            for i in range(3):
                for j in range(3):
                    if board[i][j] == '':
                        board[i][j] = self.human
                        score = self.minimax(board, depth + 1, True)
                        board[i][j] = ''
                        best_score = min(score, best_score)
            return best_score
    
    def check_winner(self, board):
        """Returns winner symbol or None"""
        # Check rows and columns
        for i in range(3):
            if board[i][0] == board[i][1] == board[i][2] != '':
                return board[i][0]
            if board[0][i] == board[1][i] == board[2][i] != '':
                return board[0][i]
        
        # Check diagonals
        if board[0][0] == board[1][1] == board[2][2] != '':
            return board[0][0]
        if board[0][2] == board[1][1] == board[2][0] != '':
            return board[0][2]
        
        return None
    
    def is_full(self, board):
        """Check if board is full"""
        return all(board[i][j] != '' for i in range(3) for j in range(3))


def run_algorithm(ai=None, board=None):
    
    if ai is None:
        ai = TicTacToeAI(ai_symbol='O', human_symbol='X')
    
    if board is None:
        return "Board cannot be None"

    move = ai.get_best_move(board)
    
    # Add safety check for None
    if move is None:
        return "No valid moves available"
    
    print(move, type(move[0]), type(move[1]))

    grid_cell_number = rectangle_mapping.get((move[0], move[1]))

    return grid_cell_number


# Usage example
if __name__ == "__main__":
    print("Test 1: AI should block opponent's winning move")
    board1 = [
        ['', '', 'X'],
        ['X', 'O', 'O'],
        ['', '', 'X']
    ]
    print(f"Board: {board1}")
    print(f"AI move (should block at position 0,2): {run_algorithm(board=board1)}\n")
    
    # print("Test 2: AI should take winning move")
    # board2 = [
    #     ['O', 'O', ''],
    #     ['X', 'X', ''],
    #     ['', '', '']
    # ]
    # print(f"Board: {board2}")
    # print(f"AI move (should win at position 0,2): {run_algorithm(board=board2)}\n")
    
    # print("Test 3: Original example")
    # board3 = [
    #     ['X', 'O', ''],
    #     ['', 'X', ''],
    #     ['', '', '']
    # ]
    # print(f"Board: {board3}")
    # print(f"AI move (should block diagonal at 2,2): {run_algorithm(board=board3)}")