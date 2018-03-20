import collections
import curses
import math

import pyaudio


BITRATE = 16000

SCALE = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
fixed_note, fixed_octave, fixed_freq = SCALE.index('A'), 4, 440
A = 2 ** (1 / 12)


def get_freq(note, octave=4):
    _note_delta = SCALE.index(note) - fixed_note
    half_step_delta = (octave - fixed_octave) * len(SCALE) + _note_delta
    return fixed_freq * (A ** half_step_delta)


def iter_rstrip(iterable, predicate):
    buffer = collections.deque()
    for elem in iterable:
        if predicate(elem):
            yield from buffer
            yield elem
            buffer.clear()
        else:
            buffer.append(elem)


class Sequencer:
    """
    Track notes to play.
    """
    def __init__(self):
        try:
            with open('song.txt', 'r') as file:
                self._notes = eval(file.read())
        except OSError:
            self._notes = [set() for _ in range(64)]

    def toggle_note(self, x, note):
        """
        Returns True if the note was added, False if removed.
        """
        note_set = self._notes[x]
        note_set ^= {note}
        return note in note_set

    def play_song(self):
        _p = pyaudio.PyAudio()
        stream = _p.open(
            format=_p.get_format_from_width(1),
            channels=1,
            rate=BITRATE,
            frames_per_buffer=2048,
            output=True,
        )
        length = 1 / 6
        NUMBER_OF_FRAMES = int(BITRATE * length)
        song_freqs = iter_rstrip((
            [
                get_freq(note, octave)
                for note, octave in notes
            ]
            for notes in self._notes
        ), bool)
        wavedata = ''.join(
            chr(int(sum(
                math.sin(x/((BITRATE/freq)/math.pi))*127+128
                for freq in freqs
            ))) if freqs else chr(128)
            for freqs in song_freqs
            for x in range(NUMBER_OF_FRAMES)
        )
        stream.write(wavedata)
        # stream.stop_stream()
        # stream.close()
        # _p.terminate()


class Board:
    """
    Interface between terminal and sequencer model.
    """
    def __init__(self):
        self._sequencer = Sequencer()

    def _get_note(self, y):
        return "BAGFEDC"[y % 7]

    def _to_y(self, note, octave):
        return "BAGFEDC".index(note) + (5 - octave) * 7

    def draw(self, screen):
        for y in range(21):
            attr = 0 if (y + 1) % 7 else curses.A_UNDERLINE
            for x in range(16):
                screen.addstr(y, x * 4, '--', attr)
                screen.addstr(y, x * 4 + 2, '--', attr | curses.color_pair(8))
        for x, column in enumerate(self._sequencer._notes):
            for note, octave in column:
                self._draw_note(screen, x, self._to_y(note, octave))

    def _draw_note(self, screen, x, y, is_note=True):
        if is_note:
            char = self._get_note(y)
            color = curses.color_pair(-y % 7 or 7)
        else:
            char = '-'
            color = curses.color_pair(0 if x % 4 < 2 else 8)
        screen.addstr(
            y, x, char, (0 if (y + 1) % 7 else curses.A_UNDERLINE) | color)

    def handle_click(self, *, mx, my, screen):
        if not (0 <= mx < 64 and 0 <= my < 21):
            return

        octave = 5 - my // 7
        note = self._get_note(my)

        is_note = self._sequencer.toggle_note(mx, (note, octave))
        self._draw_note(screen, mx, my, is_note)

    def handle_key(self, event):
        if event == ord(' '):
            self._sequencer.play_song()
        elif event == ord('s'):
            with open('song.txt', 'w') as file:
                file.write(repr(self._sequencer._notes))


def main():
    board = Board()
    try:
        screen = curses.initscr()
        curses.start_color()
        curses.noecho()
        curses.curs_set(0)
        screen.keypad(1)
        curses.mousemask(1)

        curses.init_pair(1, 161, 0)
        curses.init_pair(2, 209, 0)
        curses.init_pair(3, 185, 0)
        curses.init_pair(4, 106, 0)
        curses.init_pair(5, 72, 0)
        curses.init_pair(6, 62, 0)
        curses.init_pair(7, 132, 0)
        curses.init_pair(8, 8, 0)
        board.draw(screen)

        while True:
            event = screen.getch()
            if event == ord("q"): break
            elif event == curses.KEY_MOUSE:
                _, mx, my, _, btype = curses.getmouse()
                board.handle_click(mx=mx, my=my, screen=screen)
            else:
                board.handle_key(event)
    finally:
        curses.endwin()

if __name__ == '__main__':
    main()
