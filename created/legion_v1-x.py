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
        self.iter_of_last_update = 0

        self.num_overlords = 0

    # stagger calls per iteration to enhance speed maybe?
    async def on_step(self, iteration):
        await self.distribute_workers()
        await self.build_overlords()
        await self.scout()
        await self.build_workers()
        await self.build_queens()
        await self.inject_larva()
        await self.build_extractor()
        await self.build_offensive_buildings()
        await self.expand()
        await self.upgrade()
        await self.build_swarm()
        if self.units(MUTALISK).exists and iteration % 5 == 0:
            await self.attack(self.units(MUTALISK), iteration)
#        if self.units(ZERGLING).amount > 35 and iteration % 10 == 0:
#           await self.attack(self.units(ZERGLING))
        if self.units(ROACH).amount > 5 and iteration % 4 == 0:
            await self.attack(self.units(ROACH), iteration)

    # figure out a way for the overlords to not send themselves to their death... 
    async def scout(self):
        if self.num_overlords != self.units(OVERLORD).amount:
            self.num_overlords = self.units(OVERLORD).amount
            orders = []
            for unit, pos in zip(self.units(OVERLORD), self.expansion_locations):
                orders.append(unit.move(pos))
            await self.do_actions(orders)

    # reverse these if statements to check existance before cost...
    async def build_offensive_buildings(self):
        hatcheries = self.townhalls.ready
        if self.can_afford(SPAWNINGPOOL) and not self.units(SPAWNINGPOOL).exists and not self.already_pending(SPAWNINGPOOL):
            await self.build(SPAWNINGPOOL, near=hatcheries.first)
            return
        # I want to build this near the main ramp...
#        if self.can_afford(SPINECRAWLER) and self.units(SPINECRAWLER).amount < 4:
#            await self.build(SPINECRAWLER, near=hatcheries.first, max_distance=8)
#            return
        if self.can_afford(ROACHWARREN) and self.units(SPAWNINGPOOL).ready and not self.units(ROACHWARREN).exists and not self.already_pending(ROACHWARREN):
            await self.build(ROACHWARREN, near=hatcheries.first)
            return
        if self.can_afford(EVOLUTIONCHAMBER) and len(self.units(EVOLUTIONCHAMBER)) < 1:
            await self.build(EVOLUTIONCHAMBER, near=hatcheries.first)
        if self.can_afford(LAIR) and not self.units(LAIR).exists and not self.already_pending(LAIR):
            await self.do(self.townhalls.first.build(LAIR))
            return
        if self.can_afford(SPIRE) and self.units(SPIRE).amount < 2 and not self.already_pending(SPIRE):
            await self.build(SPIRE, near=hatcheries.first)
            return
        if self.can_afford(INFESTATIONPIT) and self.units(LAIR).ready and not self.units(INFESTATIONPIT).exists and not self.already_pending(INFESTATIONPIT):
            await self.build(INFESTATIONPIT, near=hatcheries.first)
            return
        if self.can_afford(HIVE) and not self.units(HIVE).exists and not self.already_pending(HIVE):
            await self.do(self.townhalls.first.build(HIVE))
            return
        if self.can_afford(GREATERSPIRE) and self.units(HIVE).ready \
                and self.units(SPIRE).ready and not self.already_pending(GREATERSPIRE) and not self.units(GREATERSPIRE).exists:
            await self.do(self.units(SPIRE).first.build(GREATERSPIRE))
    
    # more succint way of writing this... refactor this!!!
    # check timing to ensure spire upgrades dont retard others...
    # incorporate the army specific upgrades for roaches and hydras
    async def upgrade(self):
        if self.units(EVOLUTIONCHAMBER).ready.idle.exists:
             for evo in self.units(EVOLUTIONCHAMBER).ready.idle:
                abilities = await self.get_available_abilities(evo)
                targetAbilities = [AbilityId.RESEARCH_ZERGMISSILEWEAPONSLEVEL1, 
                                   AbilityId.RESEARCH_ZERGMISSILEWEAPONSLEVEL2, 
                                   AbilityId.RESEARCH_ZERGMISSILEWEAPONSLEVEL3, 
                                   AbilityId.RESEARCH_ZERGGROUNDARMORLEVEL1, 
                                   AbilityId.RESEARCH_ZERGGROUNDARMORLEVEL2, 
                                   AbilityId.RESEARCH_ZERGGROUNDARMORLEVEL3]
                if self.units(GREATERSPIRE).exists:
                    targetAbilities.extend([AbilityId.RESEARCH_ZERGMELEEWEAPONSLEVEL1,
                    AbilityId.RESEARCH_ZERGMELEEWEAPONSLEVEL2,
                    AbilityId.RESEARCH_ZERGMELEEWEAPONSLEVEL3])
                for ability in targetAbilities:
                    if ability in abilities:
                        if self.can_afford(ability):
                            err = await self.do(evo(ability))
                            if not err:
                                break

        if self.units(GREATERSPIRE).ready.idle.exists:
            gs = self.units(GREATERSPIRE).ready.idle.random
            abilities = await self.get_available_abilities(gs)
            targetAbilities = [AbilityId.RESEARCH_ZERGFLYERATTACKLEVEL1,
                               AbilityId.RESEARCH_ZERGFLYERATTACKLEVEL2,
                               AbilityId.RESEARCH_ZERGFLYERATTACKLEVEL3,
                               AbilityId.RESEARCH_ZERGFLYERARMORLEVEL1,
                               AbilityId.RESEARCH_ZERGFLYERARMORLEVEL2,
                               AbilityId.RESEARCH_ZERGFLYERARMORLEVEL3]
            for ability in targetAbilities:
                if self.can_afford(ability) and ability in abilities:
                    err = await self.do(gs(ability))
                    if not err:
                        break

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
#                        if self.units(HIVE).ready and self.units(BROODLORD).amount < 5 and self.can_afford(BROODLORD):
 #                          await self.do(self.units(CORRUPTOR).random.train(BROODLORD))
                        if self.can_afford(MUTALISK) and self.supply_left > 2: # 30 muta = 60 c, possibly set to max cap...
                            await self.do(larva.train(MUTALISK))
                            continue
                    if self.units(ROACHWARREN).ready and self.supply_left > 2 and self.units(ROACH).amount < 30 and self.can_afford(ROACH): # 30 roach = 60 c    
                        await self.do(larva.train(ROACH))
                        continue
#                    if self.units(ZERGLING).amount < 60 and self.can_afford(ZERGLING):  # 60 lings = 30 c
#                       await self.do(larva.train(ZERGLING))
#                       continue

    # This could be more succinct...
                       


    #need to consider a separate swarm list in order to allow damaged units to RTB
    # investigate multithreading and running each unit in own thread to avoid a double for loop...
    # might need to pursue subswarms or multiple swarms to avoid reinitializing the swarm so often
    # there is a parameter for multiprocessing...
    # This algo might only work for flying units.
    #might have to build a multiswarm architecture for overlords to pass data to mutalisks...
    # investigate periodic reinitialization to break convergance after defeating enemy army...
    async def attack(self, phys_swarm, iteration):
        if phys_swarm.amount > 3:
            orders = []
            # reinitialize swarm if needed
            if phys_swarm.amount > self.swarm_size + 3 or iteration > self.iter_of_last_update + 75:
                self.swarm_size = phys_swarm.amount
                self.phys_swarm_pos = []
                for unit in phys_swarm:
                    self.phys_swarm_pos.append([unit.position.x, unit.position.y])
                self.phys_swarm_pos = np.array(self.phys_swarm_pos)
                self.logical_swarm = P.create_swarm(n_particles=phys_swarm.amount, dimensions=2, options=self.my_options, bounds=([0,0], [self.game_info.map_size[0], self.game_info.map_size[1]]) , init_pos=self.phys_swarm_pos, clamp=(0,4.0))
                self.iter_of_last_update = iteration


            self.logical_swarm.current_cost = self.fitness(self.logical_swarm.position, phys_swarm)
            self.logical_swarm.pbest_cost = self.fitness(self.logical_swarm.pbest_pos, phys_swarm)
            self.logical_swarm.pbest_pos, self.logical_swarm.pbest_cost = P.compute_pbest(self.logical_swarm)

            if np.min(self.logical_swarm.pbest_cost) < self.logical_swarm.best_cost:
                self.logical_swarm.best_pos, self.logical_swarm.best_cost = self.my_topology.compute_gbest(self.logical_swarm)

            self.logical_swarm.velocity = self.my_topology.compute_velocity(self.logical_swarm)
            self.logical_swarm.position = self.my_topology.compute_position(self.logical_swarm)
            # Extract positions from above and issue movement/attack orders
            # loop through np array compiling positions and appending them to orders list.

            # I havent seen this behavior....
#            wounded_units = phys_swarm.filter(lambda u: u.health_percentage <= .7)
#            phys_swarm = phys_swarm.filter(lambda u: u.health_percentage > .7)

#            for unit in wounded_units:
#                unit.move(self.townhalls.first.position)
#                print("Retreating wounded unit")

            # The mutas are still ignoring nearby enemies.
            for row, unit in zip(self.logical_swarm.position, phys_swarm):
                if self.known_enemy_units.closer_than(unit.radar_range, unit.position).exists:
                    orders.append(unit.stop())
                    orders.append(unit.attack(self.known_enemy_units.closest_to(unit.position).position))
                elif self.known_enemy_units.closer_than(20, Point2(Pointlike((row[0], row[1])))).exists:
                    orders.append(unit.attack(self.known_enemy_units.closest_to(Point2(Pointlike((row[0], row[1]))))))
                else:
                    orders.append(unit.move(Point2(Pointlike((row[0], row[1])))))

            await self.do_actions(orders)


    def fitness(self, logical_swarm_pos, phys_swarm):
        #account for own health, enemy health/splash&anti air damage/
        # upgrade this function...
        # revert this back to a regular one unit function and apply the pyswarm evaluate method
        cost = []
   
        # the coefficients within can be optimized...
        if self.known_enemy_units.exists:
            for logical_pos in logical_swarm_pos:
                target_point = Point2(Pointlike((logical_pos[0], logical_pos[1])))
                cost.append( \
                        (1-(10/phys_swarm.amount))*self.known_enemy_units.closest_distance_to(target_point) + \
                        (10/phys_swarm.amount)*self.townhalls.first.distance_to(target_point) + \
                        (2 * self.known_enemy_units.closer_than(10, target_point).amount - phys_swarm.closer_than(10, target_point).amount) \
                        )
        else:
            for logical_pos in logical_swarm_pos:
                cost.append(40 / phys_swarm.center.distance2_to(Point2(Pointlike((logical_pos[0], logical_pos[1])))))
        return np.array(cost)

    # Economic Functions

    async def build_workers(self):
        for larva in self.units(LARVA).ready.noqueue:    
            if self.can_afford(DRONE) and self.workers.amount < self.townhalls.amount * 16 and self.workers.amount < 80:
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
        if self.townhalls.amount < 3 and self.can_afford(HATCHERY):
            await self.expand_now()
    

run_game(maps.get("InterloperLE"), [
    Bot(Race.Zerg, Legion()),
    Computer(Race.Protoss, Difficulty.Hard)
    ], realtime = False)
