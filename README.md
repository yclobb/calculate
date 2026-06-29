# Calculate Block
<img width="758" height="826" alt="image" src="https://github.com/user-attachments/assets/986df1b5-b542-4b34-a7c6-3a6cc7b04609" />

# Motivation
I havent built anything with pygame yet since I have only used gdscript, so I decided to make a game with pygame. I wanted my game to be somewhat original rather than copying an existing game, so I combined maths with tetris to form this game. I wanted to familiriaze myself with other languages to expand my "horizons".

Built with [pygame](https://www.pygame.org/).

- BUGS :(
- slight music shenanigans
- sometimes blocks incorrectly recognise as a combo
- sound bug when try to leave site

## Description

This game is a combination of tetris and equations, as mentioned in the motivation.
To clear lines, you must form an equation, e.g. 4 + 6 = 10
NOTE THAT YOU MUST HAVE AN = SIGN TO FORM AN EQUATION
If you get certain symbols in a cluster, they can also be cleared for points.
>>Thats about it<<
For controls, scroll down.
## Requirements

- Python 3.8+
- `pygame`

```bash
pip install pygame
```

## AI USAGE
Assistance of Ai was used to code some parts of this project, but music, design and idea have no involvement of AI
## Run

```bash
python calculate_game.py
```

## Controls

| Key            | Action          |
| -------------- | --------------- |
| `Left`/`Right` | Move piece      |
| `Up`           | Rotate piece    |
| `Down`         | Soft drop       |
| `Space`        | Hard drop       |
| `P`            | Pause / resume  |
| `M`            | Mute / unmute   |
| `R`            | Restart (after game over) |
