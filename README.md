# Boxhead Multiplayer Game

A simple top-down shooter game with LAN multiplayer support.

## Setup

1. Install Python 3.8 or higher
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Game

### Server Setup
1. On the host computer, run:
```bash
python server.py
```
2. Note the IP address shown in the console

### Client Setup
1. On each player's computer, run:
```bash
python client.py <server_ip>
```
Replace `<server_ip>` with the IP address shown on the server console.

## Controls
- WASD: Movement
- Mouse: Aim
- Left Click: Shoot
- Spacebar: Alternative shoot

## Game Features
- Multiplayer support (up to 3 players)
- Basic shooting mechanics
- Health system
- Simple enemy AI
- Obstacles and walls 