# Legion, a bot that utilizes a swarm algorithm for combat

import numpy as np
import pyswarms.backend as P
from pyswarms.backend.topology import Ring, Star
import random
import sc2
from sc2 import run_game, maps, Race, Difficulty, position
from sc2.player import Bot, Computer
from sc2.constants import *
from sc2.position import Point2, Pointlike

class Legion(sc2.BotAI):

    def __init__(self):
        self.swarm_size = 0
        self.my_topology = Star() # connect to n nearest neighbors
        self.my_options = {'c1': 4, 'c2': 1, 'w': 0.3}
        self.phys_swarm_pos = []
        self.logical_swarm = 0 #self.logical_swarm = P.create_swarm(n_particles=0, dimensions=2, options=self.my_options, bounds=([0,0], [self.game_info.map_size[0], self.game_info.map_size[1]]) , init_pos=phys_swarm_pos, clamp=(0,10))

    # stagger calls per iteration to enhance speed maybe?
    async def on_step(self, iteration):
        await self.distribute_workers()
        await self.build_overlords()
        await self.build_workers()
        await self.build_queens()
        await self.inject_larva()
        await self.build_extractor()
        await self.build_offensive_buildings()
        await self.expand()
        await self.build_swarm()
        if self.units(MUTALISK).exists and iteration % 5 == 0:
            await self.attack(self.units(MUTALISK))

    # reverse these if statements to check existance before cost...
    async def build_offensive_buildings(self):
        hatcheries = self.townhalls.ready
        if self.can_afford(SPAWNINGPOOL) and not self.units(SPAWNINGPOOL).exists:
            await self.build(SPAWNINGPOOL, near=hatcheries.first)
            return
        # this needs adjusted to check for spawning pool...
        if self.can_afford(ROACHWARREN) and self.units(SPAWNINGPOOL).ready and not self.units(ROACHWARREN).exists:
            await self.build(ROACHWARREN, near=hatcheries.first)
            return
        if self.can_afford(LAIR) and not self.units(LAIR).exists:
            await self.do(self.townhalls.first.build(LAIR))
            return
        if self.can_afford(SPIRE) and not self.units(SPIRE).exists:
            await self.build(SPIRE, near=hatcheries.first)
            return
        if self.can_afford(INFESTATIONPIT) and self.units(LAIR).ready and not self.units(INFESTATIONPIT).exists:
            await self.build(INFESTATIONPIT, near=hatcheries.first)
            return
        if self.can_afford(HIVE) and not self.units(HIVE).exists:
            await self.do(self.townhalls.first.build(HIVE))
            return
        # This probably can be reduced to a 2 argument statement... VVVV
        if self.can_afford(GREATERSPIRE) and self.units(HIVE).ready \
                and self.units(SPIRE).ready and not self.units(GREATERSPIRE).exists:
            await self.do(self.units(SPIRE).first.build(GREATERSPIRE))


    # FUTURE: incorporate dynamic composition by either tech level or AI/ML
    async def build_swarm(self):
        if self.units(SPAWNINGPOOL).ready:
            larvae = self.units(LARVA).ready.noqueue
            for larva in larvae:
                if self.supply_left > 0:
                    if self.units(SPIRE).ready:
#                        if self.units(CORRUPTOR).amount < 5 and self.can_afford(CORRUPTOR):
#                           await self.do(larva.train(CORRUPTOR))
#                           continue
#                        elif self.units(HIVE).ready and self.units(BROODLORD).amount < 5 and self.can_afford(BROODLORD):
#                           await self.do(self.units(CORRUPTOR).random.train(BROODLORD))
                        if self.can_afford(MUTALISK): # 30 muta = 60 c, possibly set to max cap...
                            await self.do(larva.train(MUTALISK))
                            continue
#                    if self.units(ROACHWARREN).ready and self.units(ROACH).amount < 30 and self.can_afford(ROACH): # 30 roach = 60 c
#                       await self.do(larva.train(ROACH))
#                       continue
#                   if self.units(ZERGLING).amount < 60 and self.can_afford(ZERGLING):  # 60 lings = 30 c
#                       await self.do(larva.train(ZERGLING))
#                       continue
 

    #need to consider a separate swarm list in order to allow damaged units to RTB
    # investigate multithreading and running each unit in own thread to avoid a double for loop...
    # might need to pursue subswarms or multiple swarms to avoid reinitializing the swarm so often
    # there is a parameter for multiprocessing...
    # This algo might only work for flying units.
    #might have to build a multiswarm architecture for overlords to pass data to mutalisks...
    async def attack(self, phys_swarm):
        if phys_swarm.amount > 10:
            orders = []
            # reinitialize swarm if needed
            if phys_swarm.amount > self.swarm_size + 3:
                self.swarm_size = phys_swarm.amount
                self.phys_swarm_pos = []
                for unit in phys_swarm:
                    self.phys_swarm_pos.append([unit.position.x, unit.position.y])
                self.phys_swarm_pos = np.array(self.phys_swarm_pos)

                self.logical_swarm = P.create_swarm(n_particles=phys_swarm.amount, dimensions=2, options=self.my_options, bounds=([0,0], [self.game_info.map_size[0], self.game_info.map_size[1]]) , init_pos=self.phys_swarm_pos, clamp=(0,4.0))
                
            self.logical_swarm.current_cost = self.fitness(self.logical_swarm.position, phys_swarm)
            self.logical_swarm.pbest_cost = self.fitness(self.logical_swarm.pbest_pos, phys_swarm)
            self.logical_swarm.pbest_pos, self.logical_swarm.pbest_cost = P.compute_pbest(self.logical_swarm)

            if np.min(self.logical_swarm.pbest_cost) < self.logical_swarm.best_cost:
                self.logical_swarm.best_pos, self.logical_swarm.best_cost = self.my_topology.compute_gbest(self.logical_swarm)

            self.logical_swarm.velocity = self.my_topology.compute_velocity(self.logical_swarm)
            self.logical_swarm.position = self.my_topology.compute_position(self.logical_swarm)
            # Extract positions from above and issue movement/attack orders
            # loop through np array compiling positions and appending them to orders list.
           
            # The mutas are still ignoring nearby enemies.
            for row, unit in zip(self.logical_swarm.position, phys_swarm):
                if self.known_enemy_units.closer_than(unit.radar_range, unit.position).exists:
                    orders.append(unit.stop())
                    orders.append(unit.attack(self.known_enemy_units.closest_to(unit.position).position))
                elif self.known_enemy_units.exists:
                    orders.append(unit.attack(self.known_enemy_units.closest_to(Point2(Pointlike((row[0], row[1]))))))
                else:
                    orders.append(unit.move(Point2(Pointlike((row[0], row[1])))))
#                    if self.known_enemy_units.in_attack_range_of(unit).exists:
 #                       orders.append(unit.attack(self.known_enemy_units.closest_to(unit.position).position))

            await self.do_actions(orders)


    def fitness(self, logical_swarm_pos, phys_swarm):
        #account for own health, enemy health/splash&anti air damage/
        # upgrade this function...
        # revert this back to a regular one unit function and apply the pyswarm evaluate method
        cost = []
   
        if self.known_enemy_units.exists:
            for logical_pos in logical_swarm_pos:
                cost.append(self.known_enemy_units.closest_distance_to(Point2(Pointlike((logical_pos[0], logical_pos[1])))))
        else:
            for logical_pos in logical_swarm_pos:
                cost.append(1 / phys_swarm.center.distance2_to(Point2(Pointlike((logical_pos[0], logical_pos[1])))))
        return np.array(cost)
#scouting...        else:
#           for logical_pos in logical_swarm_pos:
#               cost.append(self.known_enemy_units.closest_distance_to(Point2(Pointlike(logical_pos[0], logical_pos[1]))))

    # Economic Functions
    # Theres a bug resulting in overproduction of overlords and workers as well as 2 extra expansions....

    async def build_workers(self):
        for larva in self.units(LARVA).ready.noqueue:    
            if self.can_afford(DRONE) and self.workers.amount < self.townhalls.amount * 12:
                await self.do(larva.train(DRONE))

    async def build_queens(self):    
        if self.units(SPAWNINGPOOL).ready.exists:
            for hatchery in self.units(HATCHERY).ready.noqueue:
                if self.can_afford(QUEEN) and self.units(QUEEN).amount < self.townhalls.amount:
                    await self.do(hatchery.train(QUEEN))

    async def inject_larva(self):
        for queen, hatchery in zip(self.units(QUEEN).idle, self.townhalls.ready):
            abilities = await self.get_available_abilities(queen)
            if AbilityId.EFFECT_INJECTLARVA in abilities:
                await self.do(queen(EFFECT_INJECTLARVA, hatchery))

    async def build_overlords(self):
        if self.supply_left < 9 and self.units(OVERLORD).amount < 26:
            larvae = self.units(LARVA).ready.noqueue
            for larva in larvae:
                if self.can_afford(OVERLORD) and not self.already_pending(OVERLORD):
                    await self.do(larva.train(OVERLORD))

    async def build_extractor(self):
        for hatchery in self.units(HATCHERY).ready:
            vespene = self.state.vespene_geyser.closer_than(15.0, hatchery)
            for v in vespene:
                if not self.can_afford(EXTRACTOR):
                    break
                worker = self.select_build_worker(v.position)
                if worker is None:
                    break
                if not self.units(EXTRACTOR).closer_than(1.0, v).exists:
                    await self.do(worker.build(EXTRACTOR, v))

    # upgrade the logic of this to expand when a base becomes exhausted...
    async def expand(self):
        if self.townhalls.amount < 5 and self.can_afford(HATCHERY):
            await self.expand_now()
    

run_game(maps.get("InterloperLE"), [
    Bot(Race.Zerg, Legion()),
    Computer(Race.Protoss, Difficulty.Hard)
    ], realtime = False)
