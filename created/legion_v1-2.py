# Legion, a bot that utilizes a swarm algorithm for combat

import random
import sc2
from sc2 import run_game, maps, Race, Difficulty
from sc2.player import Bot, Computer
from sc2.constants import *

class Legion(sc2.BotAI):
    
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
        if iteration % 5 == 0:
            await self.attack()

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
                        if self.units(CORRUPTOR).amount < 5 and self.can_afford(CORRUPTOR):
                            await self.do(larva.train(CORRUPTOR))
                            continue
                        elif self.units(HIVE).ready and self.units(BROODLORD).amount < 5 and self.can_afford(BROODLORD):
                            await self.do(self.units(CORRUPTOR).random.train(BROODLORD))
                        elif self.can_afford(MUTALISK): # 30 muta = 60 c, possibly set to max cap...
                            await self.do(larva.train(MUTALISK))
                            continue
                    if self.units(ROACHWARREN).ready and self.units(ROACH).amount < 30 and self.can_afford(ROACH): # 30 roach = 60 c
                        await self.do(larva.train(ROACH))
                        continue
                    if self.units(ZERGLING).amount < 60 and self.can_afford(ZERGLING):  # 60 lings = 30 c
                        await self.do(larva.train(ZERGLING))
                        continue
                                   
    #need to consider a separate swarm list in order to allow damaged units to RTB
    # investigate multithreading and running each unit in own thread to avoid a double for loop...
    async def attack(self):
        orders = []
        swarm = self.units.of_type({UnitTypeId.ZERGLING, UnitTypeId.ROACH, UnitTypeId.CORRUPTOR, UnitTypeId.MUTALISK, UnitTypeId.BROODLORD})
        for hunter in swarm:
            if self.known_enemy_units.exists:
                neighbors = \
                        swarm.prefer_close_to(hunter.position).take(3, require_all=False)
                best_local_position = hunter.position
                hunter_fitness = self.fitness(hunter)
                for n in neighbors:
                    if self.fitness(n) > hunter_fitness:
                        best_local_position = n.position

                    orders.append(hunter.move(n.position))
                    orders.append(hunter.attack(self.known_enemy_units.closest_to(n.position)))
            elif swarm.amount > 90:
                orders.append(hunter.move(random.choice(self.enemy_start_locations)))

        await self.do_actions(orders)


    def fitness(self, swarm_unit):
        #account for own health, enemy health/splash&anti air damage/
        # upgrade this function...
        if self.known_enemy_units.exists:
            return 1 / swarm_unit.distance_to(self.known_enemy_units.center)
        else:
            return 0

    # Economic Functions
    # Theres a bug resulting in overproduction of overlords and workers as well as 2 extra expansions....

    async def build_workers(self):
        for larva in self.units(LARVA).ready.noqueue:    
            if self.can_afford(DRONE) and self.workers.amount < 36:
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
        if self.supply_left < 9 and not self.already_pending(OVERLORD):
            larvae = self.units(LARVA).ready.noqueue
            for larva in larvae:
                if self.can_afford(OVERLORD):
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

    async def expand(self):
        if self.townhalls.amount < 3 and self.can_afford(HATCHERY):
            await self.expand_now()
    

run_game(maps.get("AbyssalReefLE"), [
    Bot(Race.Zerg, Legion()),
    Computer(Race.Zerg, Difficulty.Hard)
    ], realtime = False)
