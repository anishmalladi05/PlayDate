import time
import board
import busio
import digitalio
import adafruit_ssd1306
import random

# 1. Initialize I2C and Display
i2c = busio.I2C(board.SCL, board.SDA)
display = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c, addr=0x3C)

display.fill(0)
display.show()

# 2. Setup Button on Pin D0
button = digitalio.DigitalInOut(board.D0)
button.direction = digitalio.Direction.INPUT
button.pull = digitalio.Pull.UP

# 3. Game Variables
ground_y = 31
dino_x = 8
dino_y = float(ground_y - 12)
dino_vy = 0.0
is_jumping = False
is_ducking = False
hold_counter = 0
frame_counter = 0
score_counter = 0

obs_x = 128.0
obs_type = 0
obs_w = 6
obs_h = 7  # Fixed initial height to match cactus height
obs_y = ground_y - obs_h  # Perfectly aligned to ground line from the very first frame

# Cluster tracking for birds
birds_remaining_in_cluster = 0

score = 0
high_score = 0
game_speed = 6.0
game_state = "PLAYING"

# --- Custom Pixel Numbers (Width: 3, Height: 5) ---
NUMS = {
    '0': [1,1,1, 1,0,1, 1,0,1, 1,0,1, 1,1,1],
    '1': [0,1,0, 1,1,0, 0,1,0, 0,1,0, 1,1,1],
    '2': [1,1,1, 0,0,1, 1,1,1, 1,0,0, 1,1,1],
    '3': [1,1,1, 0,0,1, 1,1,1, 0,0,1, 1,1,1],
    '4': [1,0,1, 1,0,1, 1,1,1, 0,0,1, 0,0,1],
    '5': [1,1,1, 1,0,0, 1,1,1, 0,0,1, 1,1,1],
    '6': [1,1,1, 1,0,0, 1,1,1, 1,0,1, 1,1,1],
    '7': [1,1,1, 0,0,1, 0,0,1, 0,0,1, 0,0,1],
    '8': [1,1,1, 1,0,1, 1,1,1, 1,0,1, 1,1,1],
    '9': [1,1,1, 1,0,1, 1,1,1, 0,0,1, 1,1,1]
}

# --- Custom Pixel Labels ("S", "C", "H", "I") ---
LABELS = {
    'S': [1,1,1, 1,0,0, 1,1,1, 0,0,1, 1,1,1],
    'C': [1,1,1, 1,0,0, 1,0,0, 1,0,0, 1,1,1],
    'H': [1,0,1, 1,0,1, 1,1,1, 1,0,1, 1,0,1],
    'I': [1,1,1, 0,1,0, 0,1,0, 0,1,0, 1,1,1]
}

def draw_number_large(num_val, start_x, start_y):
    s_val = str(num_val)
    cur_x = start_x
    for char in s_val:
        if char in NUMS:
            pattern = NUMS[char]
            idx = 0
            for r in range(5):
                for c in range(3):
                    if pattern[idx] == 1:
                        display.pixel(cur_x + (c * 2), start_y + (r * 2), 1)
                        display.pixel(cur_x + (c * 2) + 1, start_y + (r * 2), 1)
                        display.pixel(cur_x + (c * 2), start_y + (r * 2) + 1, 1)
                        display.pixel(cur_x + (c * 2) + 1, start_y + (r * 2) + 1, 1)
                    idx += 1
        cur_x += 8

def draw_label(char1, char2, start_x, start_y):
    for ch, offset in zip([char1, char2], [0, 5]):
        if ch in LABELS:
            pattern = LABELS[ch]
            idx = 0
            for r in range(5):
                for c in range(3):
                    if pattern[idx] == 1:
                        display.pixel(start_x + offset + c, start_y + r, 1)
                    idx += 1

# Original original dino frames (Width: 8, Height: 12)
dino_frame1 = bytearray([
    0x0F, 0x00, 0x1F, 0x00, 0x1A, 0x00, 0x1F, 0x00,
    0x08, 0x80, 0x0C, 0xC0, 0x0F, 0xE0, 0x04, 0x40,
    0x06, 0x60, 0x05, 0x20, 0x04, 0x10, 0x02, 0x20
])

dino_frame2 = bytearray([
    0x0F, 0x00, 0x1F, 0x00, 0x1A, 0x00, 0x1F, 0x00,
    0x08, 0x80, 0x0C, 0xC0, 0x0F, 0xE0, 0x04, 0x40,
    0x06, 0x60, 0x05, 0x20, 0x08, 0x40, 0x10, 0x80
])

# Fully filled-in solid cacti pixel art
cactus1 = bytearray([0x38, 0x38, 0xFF, 0xFF, 0x38, 0x38, 0x38])
cactus2 = bytearray([0x6C, 0x6C, 0xFF, 0xFF, 0xFF, 0x6C, 0x6C])

# 4-row tall bird frames (Flapping animation)
bird_frame1 = bytearray([0x0F, 0x3F, 0x7E, 0x2C])
bird_frame2 = bytearray([0x30, 0x7F, 0xFF, 0x18])

def draw_sprite(x, y, w, h, data):
    ix, iy = int(x), int(y)
    if ix < -w or ix >= 128 or iy < -h or iy >= 32: return
    byte_index = 0
    for row in range(h):
        for col in range(w):
            if data[byte_index] & (0x80 >> col):
                display.pixel(ix + col, iy + row, 1)
        byte_index += 1

def draw_ground():
    display.line(0, ground_y, 127, ground_y, 1)

# --- Main Game Loop ---
while True:
    if game_state == "PLAYING":
        display.fill(0)
        frame_counter += 1
        score_counter += 1
        
        if score_counter >= 25:
            score += 1
            score_counter = 0
            if score % 3 == 0:
                game_speed += 0.5
        
        draw_ground()
        
        # --- Handle Input: Tap to jump, hold to duck ---
        if not button.value:
            if is_jumping:
                hold_counter += 1
                if hold_counter > 2:
                    is_jumping = False
                    is_ducking = True
                    dino_vy = 0.0
            elif not is_ducking:
                dino_vy = -5.0
                is_jumping = True
                hold_counter = 0
        else:
            hold_counter = 0
            if is_ducking:
                is_ducking = False

        # --- Physics & Height Control ---
        if is_jumping:
            dino_y += dino_vy
            dino_vy += 1.8
            if dino_y >= ground_y - 12:
                dino_y = float(ground_y - 12)
                is_jumping = False
                dino_vy = 0.0
                frame_counter = 0
            current_dino_h = 12
        elif is_ducking:
            dino_y = float(ground_y - 6)
            current_dino_h = 6
        else:
            dino_y = float(ground_y - 12)
            current_dino_h = 12

        # --- Obstacle Movement & Cluster Spawning ---
        obs_x -= game_speed
        anim_frame = (frame_counter // 4) % 2

        if obs_x < -16:
            if birds_remaining_in_cluster > 0:
                obs_type = 2
                obs_y = 20
                obs_x = 128.0 + random.randint(3, 7)
                birds_remaining_in_cluster -= 1
            else:
                obs_x = 128.0 + random.randint(0, 30)
                rand_val = random.random()
                if score > 1 and rand_val < 0.50:
                    obs_type = 2
                    obs_y = 20
                    birds_remaining_in_cluster = 1
                else:
                    obs_type = random.choice([0, 1])
                    obs_y = ground_y - 7

        # --- Draw Obstacle ---
        if obs_type == 0:
            draw_sprite(obs_x, obs_y, 6, 7, cactus1)
            curr_obs_w, curr_obs_h = 6, 7
        elif obs_type == 1:
            draw_sprite(obs_x, obs_y, 6, 7, cactus2)
            curr_obs_w, curr_obs_h = 6, 7
        else:
            if anim_frame == 0:
                draw_sprite(obs_x, obs_y, 8, 4, bird_frame1)
            else:
                draw_sprite(obs_x, obs_y, 8, 4, bird_frame2)
            curr_obs_w, curr_obs_h = 8, 4

        # --- Draw Original Dino Safely ---
        if is_jumping:
            draw_sprite(dino_x, dino_y, 8, 12, dino_frame1)
        elif is_ducking:
            draw_sprite(dino_x, dino_y, 8, 12, dino_frame1)
        else:
            if anim_frame == 0:
                draw_sprite(dino_x, dino_y, 8, 12, dino_frame1)
            else:
                draw_sprite(dino_x, dino_y, 8, 12, dino_frame2)

        # --- Render Score ---
        draw_number_large(score, 100, 2)

        # --- Collision Detection ---
        if (dino_x + 6 > obs_x) and (dino_x + 2 < obs_x + curr_obs_w) and \
           (dino_y + current_dino_h - 1 > obs_y) and (dino_y + 1 < obs_y + curr_obs_h):
            
            display.invert(True)
            time.sleep(0.15)
            display.invert(False)
            
            if score > high_score:
                high_score = score
                
            game_state = "GAME_OVER"
            time.sleep(0.3)

        display.show()
        time.sleep(0.015)

    elif game_state == "GAME_OVER":
        display.fill(0)
        
        draw_label('S', 'C', 15, 6)
        draw_number_large(score, 10, 16)
        
        draw_label('H', 'I', 85, 6)
        draw_number_large(high_score, 80, 16)
        
        display.show()

        if not button.value:
            score = 0
            score_counter = 0
            game_speed = 6.0
            obs_x = 128.0
            dino_y = float(ground_y - 12)
            is_jumping = False
            is_ducking = False
            obs_type = 0
            obs_h = 7
            obs_y = ground_y - obs_h
            birds_remaining_in_cluster = 0
            time.sleep(0.3)
            game_state = "PLAYING"

        time.sleep(0.05)
