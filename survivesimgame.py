import random
import time
import os
from enum import Enum, auto

# Simulation constants
TIME_STEP_MINUTES = 30
TICK_SLEEP_SECONDS = 0.2
MAX_SLEEP_HOURS = 12

# Tile constants
TILE_EMPTY = "."
TILE_RIVER = "="
TILE_TREE = "Y"
TILE_LOG = "L"
TILE_STOCK = "P"

class TimePeriod(Enum):
    DAWN = auto()
    MORNING = auto()
    AFTERNOON = auto()
    DUSK = auto()
    NIGHT = auto()

class Survivor:
    def __init__(self):
        self.x = 20
        self.y = 10
        self.food = 25  # Was 15
        self.food_types = {"fish": 0, "berries": 0, "meat": 0, "jerky": 0}
        self.shelter = {
            "type": "tent",
            "level": 1,
            "bed_pos": (self.x, self.y),
            "stockpile_pos": None,
            "tiles": [
                (self.x-1, self.y-1, "T"),
                (self.x, self.y-1, "T"),
                (self.x+1, self.y-1, "T"),
                (self.x-1, self.y, "T"),
                (self.x+1, self.y, "T"),
                (self.x-1, self.y+1, "T"),
                (self.x, self.y+1, "T"),
                (self.x+1, self.y+1, "T")
            ],
            "has_bed": True,
            "has_stockpile": False,
            "logs": 0
        }
        self.day = 0
        self.time = 600  # Start at 6:00 AM (24-hour time in minutes)
        self.time_period = TimePeriod.DAWN
        self.season = "Spring"
        self.weather = "Clear"
        self.alive = True
        self.skills = {"fishing": 1.2, "hunting": 1.2, "building": 1.0}
        self.current_action = "Idle"
        self.last_food_day = 0
        self.consecutive_nights_survived = 0
        self.energy = 100
        self.sleeping = False
        # Track sleep in minutes for clarity (accumulated minutes slept today)
        self.sleep_accumulated = 0  # minutes
        self.sleep_deficit = 0
        self.max_sleep_per_day = MAX_SLEEP_HOURS * 60  # minutes
    

    def update_time(self):
        self.time += TIME_STEP_MINUTES
        if self.time >= 1440:
            self.time -= 1440
            self.day += 1
            self.update_season()
            self.update_weather()
            self.eat_food()

        if 300 <= self.time < 420:
            self.time_period = TimePeriod.DAWN
        elif 420 <= self.time < 720:
            self.time_period = TimePeriod.MORNING
        elif 720 <= self.time < 1020:
            self.time_period = TimePeriod.AFTERNOON
        elif 1020 <= self.time < 1200:
            self.time_period = TimePeriod.DUSK
        else:
            self.time_period = TimePeriod.NIGHT

        if self.sleeping:
            # Accumulate minutes slept by the time step amount
            self.sleep_accumulated += TIME_STEP_MINUTES
            # Restore energy faster during night
            if self.time_period == TimePeriod.NIGHT:
                self.energy = min(100, self.energy + 20)
            else:
                self.energy = min(100, self.energy + 10)

        if self.time == 0:
            if self.sleep_accumulated < self.max_sleep_per_day:
                # sleep_deficit stores hours short as an integer number of hours
                hours_short = (self.max_sleep_per_day - self.sleep_accumulated) / 60
                self.sleep_deficit += int(hours_short)
            self.sleep_accumulated = 0
        # Detect transition into night to reset per-night counter
        if self.time_period == TimePeriod.NIGHT and self._prev_time_period != TimePeriod.NIGHT:
            self._counted_this_night = False

        self._prev_time_period = self.time_period

    def format_time(self):
        hours = self.time // 60
        minutes = self.time % 60
        return f"{hours:02d}:{minutes:02d}"

    def update_season(self):
        seasons = ["Spring", "Summer", "Fall", "Winter"]
        self.season = seasons[(self.day // 10) % 4]

    def update_weather(self):
        weather_options = {
            "Spring": ["Clear"]*8 + ["Rainy"]*5 + ["Windy"]*2,
            "Summer": ["Clear"]*10 + ["Hot"]*4 + ["Stormy"]*1,
            "Fall": ["Clear"]*8 + ["Windy"]*5 + ["Foggy"]*2,
            "Winter": ["Snowy"]*5 + ["Cold"]*8 + ["Blizzard"]*2
        }
        self.weather = random.choice(weather_options[self.season])

    def gather_food(self):
        if self.sleeping:
            return
            
        current_tile = world[self.y][self.x]
        if current_tile == "=" and self.season != "Winter":
            if random.random() < 0.85:  # Was 0.7
                gained = max(1, int(random.gauss(2.5 * self.skills["fishing"], 1)))  # Was 2*
                self.food_types["fish"] += gained
                self.skills["fishing"] += 0.05
                self.current_action = f"Fishing (+{gained})"
                self.last_food_day = self.day
                self.energy -= 6
            else:
                self.current_action = "Fishing (no catch)"
                self.energy -= 3
        elif current_tile == "Y":
            gained = max(1, int(random.gauss(2 * self.skills["hunting"], 1)))
            self.food_types["meat"] += gained
            self.skills["hunting"] += 0.1
            self.current_action = f"Hunting (+{gained})"
            self.last_food_day = self.day
            self.energy -= 8
        elif self.season == "Spring":
            self.food_types["berries"] += 1
            self.current_action = "Foraging berries (+1)"
            self.last_food_day = self.day
            self.energy -= 3

    def spoil_food(self):
        for food in ["fish", "berries", "meat"]:
            if self.food_types[food] > 0:
                spoiled = int(self.food_types[food] * 0.15)  # Was 0.3
                self.food_types[food] -= spoiled
        # Jerky does not spoil

    def can_chop_here(self, x, y):
        return (0 <= x < width and 0 <= y < height and 
                world[y][x] == "Y" and 
                (x, y) not in [(tx, ty) for tx, ty, _ in self.shelter["tiles"]])

    def chop_tree(self):
        if self.energy < 15:
            return False
            
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                x, y = self.x + dx, self.y + dy
                if self.can_chop_here(x, y):
                    world[y][x] = "L"
                    self.energy -= 15
                    self.skills["building"] += 0.2
                    self.current_action = "Chopped tree into logs"
                    return True
        return False

    def create_stockpile(self):
        if self.energy < 10 or self.shelter["level"] == 0:
            return False
            
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                x, y = self.x + dx, self.y + dy
                if (0 <= x < width and 
                    0 <= y < height and
                    world[y][x] == "." and
                    (abs(dx) + abs(dy)) > 0 and  # Don't place on self
                    any(abs(tx - x) <= 2 and abs(ty - y) <= 2 
                        for tx, ty, _ in self.shelter["tiles"])):
                    world[y][x] = "P"
                    self.energy -= 10
                    self.current_action = "Created lumber stockpile"
                    return True
        return False

    def gather_logs(self):
        if self.energy < 5:
            return False
            
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                x, y = self.x + dx, self.y + dy
                if 0 <= x < width and 0 <= y < height and world[y][x] == "L":
                    world[y][x] = "."
                    self.energy -= 5
                    self.current_action = "Gathered logs"
                    self.shelter["logs"] += 1
                    return True
        return False

    def can_build_here(self, size):
        for dy in range(-size, size+1):
            for dx in range(-size, size+1):
                x, y = self.x + dx, self.y + dy
                if not (0 <= x < width and 0 <= y < height):
                    return False
                if world[y][x] not in [".", "Y", "L", "P"]:
                    return False
        return True
    
    def build_shelter(self):
        if self.sleeping:
            return False
            
        if self.shelter["level"] == 0 and self.shelter["logs"] < 3:
            self.current_action = "Need 3 logs to build tent"
            return False
        if self.shelter["level"] == 1 and self.shelter["logs"] < 10:
            self.current_action = "Need 10 logs to build cabin"
            return False
            
        required_clearance = 1 if self.shelter["level"] == 0 else 2
        if not self.can_build_here(required_clearance):
            self.current_action = "Not enough clear space!"
            return False
            
        if self.shelter["level"] == 0:
            adjacent_trees = 0
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    if world[self.y + dy][self.x + dx] == "Y":
                        adjacent_trees += 1
            if adjacent_trees < 3:
                self.current_action = "Need more trees nearby!"
                return False
        
        self.skills["building"] += 0.05
        self.energy -= 10
        
        if self.shelter["level"] == 0:
            self.shelter["tiles"] = []
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    if not (dx == 0 and dy == 0) and not (dx == -1 and dy == 0):
                        self.shelter["tiles"].append((self.x + dx, self.y + dy, "T"))
                        world[self.y + dy][self.x + dx] = "T"
            
            self.shelter["level"] = 1
            self.shelter["type"] = "tent"
            self.shelter["bed_pos"] = (self.x, self.y)
            self.shelter["has_bed"] = True
            self.shelter["logs"] -= 3
            self.current_action = "Built a tent (enter from left)!"
            return True
            
        elif self.shelter["level"] == 1 and self.skills["building"] >= 1.5:
            self.shelter["tiles"] = []
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    is_wall = (abs(dx) == 2 or abs(dy) == 2)
                    is_entrance = (dx == -2 and dy == 0)
                    if is_wall and not is_entrance:
                        self.shelter["tiles"].append((self.x + dx, self.y + dy, "C"))
                        world[self.y + dy][self.x + dx] = "C"
            
            self.shelter["level"] = 2
            self.shelter["type"] = "cabin"
            self.shelter["bed_pos"] = (self.x, self.y)
            self.shelter["stockpile_pos"] = (self.x + 1, self.y)
            self.shelter["has_bed"] = True
            self.shelter["has_stockpile"] = True
            self.shelter["logs"] -= 10
            self.current_action = "Built a cabin (enter from left)!"
            return True
            
        return False

    def add_bed(self):
        if self.sleeping or self.shelter["level"] == 0:
            return False
            
        if self.shelter["level"] == 1:
            self.shelter["has_bed"] = True
            self.current_action = "Bed placed in tent"
            return True
        elif self.shelter["level"] == 2:
            self.shelter["has_bed"] = True
            self.current_action = "Bed placed in cabin"
            return True
        return False

    def add_stockpile(self):
        if self.sleeping or self.shelter["level"] < 2:
            return False
            
        if self.shelter["level"] == 2 and not self.shelter["has_stockpile"]:
            self.shelter["has_stockpile"] = True
            self.current_action = "Stockpile placed in cabin"
            return True
        return False
            
    def sleep(self):
        if not self.shelter["has_bed"]:
            return False
            
        if not self.sleeping:
            self.sleeping = True
            self.current_action = "Sleeping..."
            return True
        return False

    def wake_up(self):
        if self.sleeping:
            if (self.sleep_accumulated >= self.max_sleep_per_day or 
                self.time >= 660):
                self.sleeping = False
                if self.sleep_accumulated >= self.max_sleep_per_day:
                    self.sleep_deficit = 0
                self.current_action = "Woke up refreshed"
                return True
        return False

    def survive_night(self):
        if self.time_period != TimePeriod.NIGHT:
            return
            
        if self.sleeping:
            return
        
        self.eat_food()  # <-- Add here
        
        base_consumption = 1.0 if self.shelter["level"] > 0 else 2.0  # Was 1.5/3.0
        
        if self.sleep_deficit > 0:
            base_consumption *= 1.0 + (self.sleep_deficit * 0.1)
            
        if self.shelter["level"] == 0:
            base_consumption *= 2.0
            if self.weather in ["Rainy", "Stormy", "Snowy", "Blizzard"]:
                base_consumption *= 1.5
        
        if self.shelter["has_bed"]:
            base_consumption *= 0.6
        if self.shelter["has_stockpile"]:
            base_consumption *= 0.7
        
        if self.season == "Winter":
            base_consumption *= 1.3
        
        consumed = max(0.5, base_consumption)
        self.food -= consumed
        self.energy -= 10
        
        if self.food <= 0 or self.energy <= 0:
            self.alive = False
        else:
            # Count this survived night only once per night
            if not getattr(self, '_counted_this_night', False):
                self.consecutive_nights_survived += 1
                self._counted_this_night = True
                if self.shelter["level"] > 0:
                    self.skills["building"] += 0.1

    def move_toward(self, target):
        if self.sleeping:
            return False
            
        nearest = None
        min_dist = float('inf')
        for y in range(height):
            for x in range(width):
                if world[y][x] == target:
                    dist = abs(x - self.x) + abs(y - self.y)
                    if dist < min_dist:
                        min_dist = dist
                        nearest = (x, y)
        
        if nearest:
            dx = 1 if nearest[0] > self.x else -1 if nearest[0] < self.x else 0
            dy = 1 if nearest[1] > self.y else -1 if nearest[1] < self.y else 0
            self.x = max(1, min(width - 2, self.x + dx))
            self.y = max(1, min(height - 2, self.y + dy))
            self.energy -= 2
            return True
        return False

    def move_toward_shelter(self):
        if not self.shelter["tiles"]:
            return False
            
        shelter_center = (
            sum(x for x, y, _ in self.shelter["tiles"]) // len(self.shelter["tiles"]),
            sum(y for x, y, _ in self.shelter["tiles"]) // len(self.shelter["tiles"])
        )
        
        dx = 1 if shelter_center[0] > self.x else -1 if shelter_center[0] < self.x else 0
        dy = 1 if shelter_center[1] > self.y else -1 if shelter_center[1] < self.y else 0
        
        self.x = max(1, min(width - 2, self.x + dx))
        self.y = max(1, min(height - 2, self.y + dy))
        self.energy -= 2
        return True

    def can_move_to(self, x, y):
        if not (0 <= x < width and 0 <= y < height):
            return False
            
        if self.shelter["level"] > 0:
            if (x, y) == self.shelter["bed_pos"]:
                return True
            if self.shelter["level"] == 2:
                if (x, y) == self.shelter["stockpile_pos"]:
                    return True
                if (x, y) == (self.shelter["bed_pos"][0], self.shelter["bed_pos"][1] + 1):
                    return True
            if self.shelter["level"] == 1 and (x, y) == (self.shelter["bed_pos"][0] - 1, self.shelter["bed_pos"][1]):
                return True
            if self.shelter["level"] == 2 and (x, y) == (self.shelter["bed_pos"][0] - 2, self.shelter["bed_pos"][1]):
                return True
                
        return world[y][x] in [".", "=", "Y", "T", "C", "L", "P"]

    def wander(self):
        if self.sleeping:
            return
            
        self.x = max(1, min(width - 2, self.x + random.randint(-1, 1)))
        self.y = max(1, min(height - 2, self.y + random.randint(-1, 1)))
        self.current_action = "Exploring"
        self.energy -= 1
    
    def eat_food(self):
        # Prioritize eating perishable food first
        for food in ["berries", "fish", "meat", "jerky"]:
            while self.food < 25 and self.food_types[food] > 0:
                self.food_types[food] -= 1
                self.food += 1

    def decide_action(self):
        if self.sleeping:
            if self.energy > 80 or self.time_period not in [TimePeriod.NIGHT, TimePeriod.DAWN]:
                self.wake_up()
            return
                
        if (self.energy < 20 or 
            (self.time_period == TimePeriod.NIGHT and self.shelter["has_bed"])):
            self.sleep()
            return
        
        sleep_urgency = (
            (self.time_period == TimePeriod.NIGHT and self.shelter["has_bed"]) or
            (self.energy < 30) or
            (self.sleep_deficit > 6)
        )
        
        if sleep_urgency and not self.sleeping and self.shelter["has_bed"]:
            if (self.x, self.y) != self.shelter["bed_pos"]:
                self.move_toward_shelter()
            else:
                self.sleep()
            return
            
        if self.food < 5 or (self.day - self.last_food_day) > 2:
            if self.season != "Winter" and random.random() < 0.7:
                if self.move_toward("="):
                    self.current_action = "Seeking fish"
                return
            else:
                if self.move_toward("Y"):
                    self.current_action = "Seeking game"
                return

        if (self.time_period == TimePeriod.AFTERNOON and 
            self.shelter["level"] < 2):
            
            needed_logs = 3 if self.shelter["level"] == 0 else 10
            if self.shelter["logs"] < needed_logs:
                if random.random() < 0.7:
                    if self.move_toward("Y"):
                        self.current_action = "Going to chop trees"
                    return
                elif self.move_toward("L"):
                    self.current_action = "Going to gather logs"
                    return
            
            if not any(c == "P" for row in world for c in row):
                if random.random() < 0.5:
                    self.create_stockpile()
                    return
            
            if self.move_toward("Y"):
                self.current_action = "Preparing to build shelter"
                return
    
        if self.season == "Summer" and random.random() < 0.6:
            self.move_toward("=")
        elif self.season == "Fall" and random.random() < 0.6:
            self.move_toward("Y")
        else:
            self.wander()

    def update(self):
        self.update_time()
        self.decide_action()
        
        if not self.sleeping:
            if world[self.y][self.x] == "=" and self.season != "Winter":
                self.gather_food()
            elif world[self.y][self.x] == "Y":
                if random.random() < 0.3:
                    self.chop_tree()
                elif self.shelter["level"] < 2 or random.random() < 0.5:
                    self.build_shelter()
                else:
                    self.gather_food()
            elif world[self.y][self.x] == "L":
                self.gather_logs()
            elif random.random() < 0.3:
                self.gather_food()

            if self.shelter["level"] > 0 and random.random() < 0.1:
                if not self.shelter["has_bed"]:
                    self.add_bed()
                elif not self.shelter["has_stockpile"]:
                    self.add_stockpile()

        self.survive_night()
        self.spoil_food()

# World Generation
width, height = 50, 20
world = [["." for _ in range(width)] for _ in range(height)]

# Rivers
for _ in range(2):
    y = random.randint(5, height-5)
    for x in range(width):
        if random.random() < 0.7:
            world[y][x] = "="
            if random.random() < 0.3:
                for dy in [-1, 1]:
                    if 0 <= y + dy < height:
                        world[y + dy][x] = "="

# Add trees, then carve clearings so clearings actually remove trees
for _ in range(5):
    cx, cy = random.randint(10, width-10), random.randint(10, height-10)
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            if 0 <= cx+dx < width and 0 <= cy+dy < height:
                if random.random() < 0.6 - (abs(dx) + abs(dy)) * 0.1:
                    world[cy+dy][cx+dx] = TILE_TREE

# Forest clearings: remove some trees inside a larger radius to create natural clearings
for _ in range(5):
    cx, cy = random.randint(10, width-10), random.randint(10, height-10)
    for dy in range(-5, 6):
        for dx in range(-5, 6):
            if (0 <= cx+dx < width and 0 <= cy+dy < height and
                abs(dx) + abs(dy) < 6 and random.random() < 0.7):
                if world[cy+dy][cx+dx] == TILE_TREE:
                    world[cy+dy][cx+dx] = TILE_EMPTY

def get_time_color(time_period):
    return {
        TimePeriod.DAWN: "\033[38;5;216m",
        TimePeriod.MORNING: "\033[93m",
        TimePeriod.AFTERNOON: "\033[97m",
        TimePeriod.DUSK: "\033[38;5;129m",
        TimePeriod.NIGHT: "\033[34m"
    }[time_period]

def draw_world(survivor):
    os.system('cls' if os.name == 'nt' else 'clear')
    
    time_color = get_time_color(survivor.time_period)
    time_name = survivor.time_period.name.lower()
    time_str = survivor.format_time()
    
    player_color = "\033[1;33m"  # Bright yellow for player
    tree_color = "\033[92m"      # Light green for trees
    river_color = "\033[96m"     # Light blue for rivers
    log_color = "\033[33m"       # Yellow for logs
    stockpile_color = "\033[33m" # Yellow for stockpiles


    for y in range(height):
        row = []
        for x in range(width):
            if y == survivor.y and x == survivor.x:
                row.append(f"{player_color}@\033[0m")
                continue
                
            shelter_tile = next((sym for (tx, ty, sym) in survivor.shelter["tiles"] 
                              if tx == x and ty == y), None)
            if shelter_tile:
                row.append(shelter_tile)
            elif (x, y) == survivor.shelter.get("bed_pos"):
                row.append("B")
            elif (x, y) == survivor.shelter.get("stockpile_pos"):
                            row.append(f"{stockpile_color}S\033[0m")
            else:
                tile = world[y][x]
                if tile == "=":  # River
                    if survivor.season == "Winter":
                        colored = f"\033[36m|\033[0m"  # Cyan for ice
                    else:
                        colored = f"{river_color}{tile}\033[0m"
                elif tile == "Y":  # Tree
                    colored = f"{tree_color}{tile}\033[0m"
                elif tile == "L":  # Logs
                    colored = f"{log_color}{tile}\033[0m"
                elif tile == "P":  # Stockpile
                    colored = f"{stockpile_color}{tile}\033[0m"
                elif tile == "*" and survivor.season == "Winter":  # Frozen river
                    colored = f"\033[36m|\033[0m"  # Cyan for ice
                else:
                    colored = tile
                
                if survivor.time_period == TimePeriod.NIGHT:
                    if any(tx == x and ty == y for (tx, ty, _) in survivor.shelter["tiles"]):
                        row.append(colored)
                    else:
                        row.append("\033[90m" + colored + "\033[0m")
                else:
                    row.append(colored)
        
        print(" ".join(row))
    
    print(f"\n{time_color}{time_str} {time_name}\033[0m | Day: {survivor.day} | Season: {survivor.season} | Weather: {survivor.weather}")
    print(f"Food: {int(survivor.food)} (Fish:{survivor.food_types['fish']} Berries:{survivor.food_types['berries']} Meat:{survivor.food_types['meat']} Jerky:{survivor.food_types['jerky']}) | Energy: {int(survivor.energy)} | Shelter: {survivor.shelter['level']}/2 ({survivor.shelter['type'] or 'none'})")
    print(f"Logs: {survivor.shelter['logs']} | Action: {survivor.current_action}")
    print(f"Skills: Fishing({survivor.skills['fishing']:.1f}) Hunting({survivor.skills['hunting']:.1f}) Building({survivor.skills['building']:.1f})")

def main():
    survivor = Survivor()
    while survivor.alive:
        draw_world(survivor)
        survivor.update()
        time.sleep(0.2)
    
    print(f"\nGame Over! Survived {survivor.day} days and {survivor.consecutive_nights_survived} nights.")

if __name__ == "__main__":
    main()