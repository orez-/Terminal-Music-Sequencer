import curses


class Sequencer:
    """
    Track notes to play.
    """
    def __init__(self):
        self._notes = [set() for _ in range(64)]

    def toggle_note(self, x, y):  # TODO: weird interface
        """
        Returns True if the note was added, False if removed.
        """
        note_set = self._notes[x]
        note_set ^= {y}
        return y in note_set


class Board:
    """
    Interface between terminal and sequencer model.
    """
    def __init__(self):
        self._sequencer = Sequencer()

    def _get_note(self, y):
        return "BAGFEDC"[y % 7]

    def draw(self, screen):
        for y in range(21):
            screen.addstr(y, 0, '-' * 64, 0 if (y + 1) % 7 else curses.A_UNDERLINE)

    def handle_click(self, *, mx, my, screen):
        if not (0 <= mx < 64 and 0 <= my < 21):
            return

        char = self._get_note(my) if self._sequencer.toggle_note(mx, my) else '-'
        color = curses.color_pair(-my % 7 or 7)
        screen.addstr(
            my, mx, char, (0 if (my + 1) % 7 else curses.A_UNDERLINE) | color)


def main():
    board = Board()
    try:
        screen = curses.initscr()
        curses.start_color()
        curses.noecho()
        curses.curs_set(0)
        screen.keypad(1)
        curses.mousemask(1)

        # raise Exception(curses.COLORS)
        # curses.init_color(1, 851, 153, 286)
        curses.init_pair(1, 161, 0)
        curses.init_pair(2, 209, 0)
        curses.init_pair(3, 185, 0)
        curses.init_pair(4, 106, 0)
        curses.init_pair(5, 72, 0)
        curses.init_pair(6, 62, 0)
        curses.init_pair(7, 132, 0)
        board.draw(screen)

        while True:
            event = screen.getch()
            if event == ord("q"): break
            elif event == curses.KEY_MOUSE:
                _, mx, my, _, btype = curses.getmouse()
                board.handle_click(mx=mx, my=my, screen=screen)
    finally:
        curses.endwin()

if __name__ == '__main__':
    main()
