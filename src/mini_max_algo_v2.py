"""
Production-Ready Tic-Tac-Toe AI
Implements optimal strategy guaranteed to never lose
"""

rectangle_mapping = {
    (0, 0): 1, (0, 1): 2, (0, 2): 3,
    (1, 0): 4, (1, 1): 5, (1, 2): 6,
    (2, 0): 7, (2, 1): 8, (2, 2): 9,
}

# All possible winning lines
LINES = [
    # Rows
    [(0,0), (0,1), (0,2)], [(1,0), (1,1), (1,2)], [(2,0), (2,1), (2,2)],
    # Columns
    [(0,0), (1,0), (2,0)], [(0,1), (1,1), (2,1)], [(0,2), (1,2), (2,2)],
    # Diagonals
    [(0,0), (1,1), (2,2)], [(0,2), (1,1), (2,0)]
]


class InvalidBoardError(Exception):
    """Raised when board state is invalid"""
    pass


class TicTacToeAI:
    """Optimal Tic-Tac-Toe AI using strategic rules"""
    
    def __init__(self, ai_symbol='O', human_symbol='X'):
        if ai_symbol == human_symbol:
            raise ValueError("AI and human symbols must be different")
        self.ai = ai_symbol
        self.human = human_symbol
    
    def get_best_move(self, board):
        """
        Returns optimal move (row, col) using priority strategy:
        1. Win immediately
        2. Block opponent win
        3. Create fork (multiple threats)
        4. Block opponent fork
        5. Take center
        6. Take opposite corner
        7. Take any corner
        8. Take any edge
        
        Raises:
            InvalidBoardError: If board state is invalid
            ValueError: If no moves available
        """
        self._validate_board(board)
        
        # Priority 1: Win
        move = self._find_winning_move(board, self.ai)
        if move: return move
        
        # Priority 2: Block
        move = self._find_winning_move(board, self.human)
        if move: return move
        
        # Priority 3: Fork
        move = self._find_fork(board, self.ai)
        if move: return move
        
        # Priority 4: Block opponent fork
        forks = self._find_all_forks(board, self.human)
        if len(forks) == 1:
            return forks[0]
        elif len(forks) > 1:
            move = self._create_forcing_threat(board)
            if move: return move
        
        # Priority 5: Center
        if board[1][1] == '':
            return (1, 1)
        
        # Priority 6: Opposite corner
        move = self._opposite_corner(board)
        if move: return move
        
        # Priority 7: Any corner
        for pos in [(0,0), (0,2), (2,0), (2,2)]:
            if board[pos[0]][pos[1]] == '':
                return pos
        
        # Priority 8: Any edge
        for pos in [(0,1), (1,0), (1,2), (2,1)]:
            if board[pos[0]][pos[1]] == '':
                return pos
        
        raise ValueError("No valid moves available")
    
    def _validate_board(self, board):
        """Validate board structure and state"""
        if not isinstance(board, list) or len(board) != 3:
            raise InvalidBoardError("Board must be 3x3 list")
        
        for row in board:
            if not isinstance(row, list) or len(row) != 3:
                raise InvalidBoardError("Each row must contain 3 elements")
        
        ai_count = sum(row.count(self.ai) for row in board)
        human_count = sum(row.count(self.human) for row in board)
        
        # Check for invalid symbols
        for row in board:
            for cell in row:
                if cell not in ['', self.ai, self.human]:
                    raise InvalidBoardError(f"Invalid symbol: {cell}")
        
        # Validate move counts (human goes first)
        if abs(ai_count - human_count) > 1:
            raise InvalidBoardError("Invalid move counts")
        
        # Check if game already won
        if self._check_winner(board):
            raise InvalidBoardError("Game already won")
    
    def _find_winning_move(self, board, player):
        """Find immediate winning move for player"""
        for i in range(3):
            for j in range(3):
                if board[i][j] == '':
                    board[i][j] = player
                    wins = self._check_winner(board) == player
                    board[i][j] = ''
                    if wins:
                        return (i, j)
        return None
    
    def _find_fork(self, board, player):
        """Find move that creates 2+ winning threats"""
        for i in range(3):
            for j in range(3):
                if board[i][j] == '':
                    board[i][j] = player
                    threats = self._count_threats(board, player)
                    board[i][j] = ''
                    if threats >= 2:
                        return (i, j)
        return None
    
    def _find_all_forks(self, board, player):
        """Find all positions that create forks"""
        forks = []
        for i in range(3):
            for j in range(3):
                if board[i][j] == '':
                    board[i][j] = player
                    if self._count_threats(board, player) >= 2:
                        forks.append((i, j))
                    board[i][j] = ''
        return forks
    
    def _create_forcing_threat(self, board):
        """Create threat that forces opponent to defend (not fork)"""
        for i in range(3):
            for j in range(3):
                if board[i][j] == '':
                    board[i][j] = self.ai
                    if self._count_threats(board, self.ai) > 0:
                        threat_pos = self._find_threat_empty(board, self.ai)
                        if threat_pos:
                            board[threat_pos[0]][threat_pos[1]] = self.human
                            opp_forks = len(self._find_all_forks(board, self.human))
                            board[threat_pos[0]][threat_pos[1]] = ''
                            board[i][j] = ''
                            if opp_forks == 0:
                                return (i, j)
                    board[i][j] = ''
        return None
    
    def _opposite_corner(self, board):
        """Take opposite corner if opponent is in corner"""
        pairs = [((0,0), (2,2)), ((0,2), (2,0))]
        for c1, c2 in pairs:
            if board[c1[0]][c1[1]] == self.human and board[c2[0]][c2[1]] == '':
                return c2
            if board[c2[0]][c2[1]] == self.human and board[c1[0]][c1[1]] == '':
                return c1
        return None
    
    def _count_threats(self, board, player):
        """Count lines with 2 player pieces and 1 empty"""
        count = 0
        for line in LINES:
            vals = [board[r][c] for r, c in line]
            if vals.count(player) == 2 and vals.count('') == 1:
                count += 1
        return count
    
    def _find_threat_empty(self, board, player):
        """Find empty position in a threat line"""
        for line in LINES:
            vals = [board[r][c] for r, c in line]
            if vals.count(player) == 2 and vals.count('') == 1:
                for r, c in line:
                    if board[r][c] == '':
                        return (r, c)
        return None
    
    def _check_winner(self, board):
        """Return winner symbol or None"""
        for line in LINES:
            vals = [board[r][c] for r, c in line]
            if vals[0] == vals[1] == vals[2] != '':
                return vals[0]
        return None


def run_algorithm(ai=None, board=None):
    """
    Run Tic-Tac-Toe AI algorithm
    
    Args:
        ai: TicTacToeAI instance (creates default if None)
        board: 3x3 board state
    
    Returns:
        Grid cell number (1-9)
    
    Raises:
        InvalidBoardError: If board is invalid
        ValueError: If no moves available
    """
    if board is None:
        raise ValueError("Board cannot be None")
    
    if ai is None:
        ai = TicTacToeAI(ai_symbol='O', human_symbol='X')
    
    move = ai.get_best_move(board)
    return rectangle_mapping[move]


# ============= TESTS =============
if __name__ == "__main__":
    def test_case(name, board, expected, description=""):
        try:
            result = run_algorithm(board=board)
            status = "✓" if (isinstance(expected, list) and result in expected) or result == expected else "✗"
            print(f"{status} {name}: {result} (expect {expected}) {description}")
        except Exception as e:
            print(f"✗ {name}: ERROR - {e}")
    
    print("="*60)
    print("BASIC STRATEGY TESTS")
    print("="*60)
    
    test_case("Win immediately", 
              [['O', 'O', ''], ['X', 'X', ''], ['', '', '']], 
              3, "- Take winning move")
    
    test_case("Block opponent", 
              [['X', 'X', ''], ['O', 'O', ''], ['', '', '']], 
              [3, 6], "- Block or win")
    
    test_case("Block diagonal", 
              [['X', 'O', ''], ['', 'X', ''], ['', '', '']], 
              9, "- Block diagonal threat")
    
    test_case("Take center", 
              [['', '', ''], ['', '', ''], ['', '', '']], 
              5, "- Empty board takes center")
    
    test_case("Edge case", 
              [['', '', 'X'], ['X', 'O', 'O'], ['', '', 'X']], 
              [1, 2, 3, 7, 8], "- Strategic positioning")
    
    print("\n" + "="*60)
    print("ERROR HANDLING TESTS")
    print("="*60)
    
    try:
        run_algorithm(board=None)
        print("✗ Null board: Should raise ValueError")
    except ValueError:
        print("✓ Null board: Correctly raises ValueError")
    
    try:
        run_algorithm(board=[['X', 'X', 'X'], ['O', 'O', ''], ['', '', '']])
        print("✗ Won game: Should raise InvalidBoardError")
    except InvalidBoardError:
        print("✓ Won game: Correctly raises InvalidBoardError")
    
    try:
        run_algorithm(board=[['X', 'X'], ['O', 'O']])
        print("✗ Wrong size: Should raise InvalidBoardError")
    except InvalidBoardError:
        print("✓ Wrong size: Correctly raises InvalidBoardError")
    
    try:
        run_algorithm(board=[['X', 'X', 'X'], ['O', 'O', 'O'], ['X', 'X', 'X']])
        print("✗ Invalid state: Should raise InvalidBoardError")
    except InvalidBoardError:
        print("✓ Invalid state: Correctly raises InvalidBoardError")
    
    print("\n" + "="*60)
    print("ALL TESTS COMPLETE")
    print("="*60)