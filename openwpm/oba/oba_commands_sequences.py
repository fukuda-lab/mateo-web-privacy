import sys
from typing import List
sys.path.append('../openwpm')
from openwpm.command_sequence import RecursiveDumpPageSourceCommand, ScreenshotFullPageCommand, CommandSequence
from openwpm.commands.browser_commands import GetCommand
from CMPB_commands import CMPBCommand, BannerInteractionNoDBSaveCommand
from bannerclick.config import *
from urllib.parse import urlparse
import random

def control_site_visit_sequence(control_site: str, next_site_rank: str = 0, clean_run: bool = False, cookie_banner_action: int = 0):
    """ Returns a command sequence that makes a clean run for a given control_site """
    
    def _control_sites_callback(success: bool, val: str = control_site) -> None:
        print(
            f"{'[CLEAN VISIT]' if clean_run else '[CONTROL VISIT]'} for {val} ran {'SUCCESSFULLY' if success else 'UNSUCCESSFULLY'}"
        )
        
    control_site_sequence = CommandSequence(
        control_site,
        site_rank=next_site_rank,
        callback=_control_sites_callback,
        reset=clean_run
    )
    domain = urlparse(control_site).netloc.split('.')[0]
    wait_time = 180 + random.randint(60, 120)
    if cookie_banner_action == 0:
        control_site_sequence.append_command(GetCommand(control_site, sleep=wait_time), timeout= wait_time + 120)
    else:
        control_site_sequence.append_command(BannerInteractionNoDBSaveCommand(control_site, sleep=wait_time, timeout= wait_time + 60, index=next_site_rank, choice=cookie_banner_action), timeout= wait_time + 120)
    control_site_sequence.append_command(ScreenshotFullPageCommand("_"), timeout= wait_time)
    control_site_sequence.append_command(RecursiveDumpPageSourceCommand(domain), timeout = wait_time)
    
    return control_site_sequence


def individual_training_visit_sequence(training_site: str, next_site_rank = None, sleep: int = 10, creation: bool = False, cookie_banner_action: int = 0):
    """ Visits one training_site """
    def _training_sites_callback(success: bool, val: str = training_site) -> None:
        print(
            f"{'[CREATION VISIT]' if creation else '[TRAINING VISIT]'} for {val} ran {'SUCCESSFULLY' if success else 'UNSUCCESSFULLY'}"
        )
        
    training_visit_sequence = CommandSequence(
        training_site,
        callback=_training_sites_callback,
    )
    
    if creation or cookie_banner_action == 0:
        training_visit_sequence.append_command(GetCommand(training_site, sleep=sleep), timeout= sleep + 180)
    # TODO: Probar con distintas choices
    else:
        training_visit_sequence.append_command(BannerInteractionNoDBSaveCommand(training_site, sleep=sleep, index=next_site_rank, timeout= sleep + 120, choice=cookie_banner_action), timeout= sleep + 180)
    
    return training_visit_sequence


def training_visits_sequence(training_sites: List[str], next_site_rank : int, cookie_banner_action: int = 0):
    command_sequences = []
    sites_remaining = training_sites.copy()
    
    while sites_remaining:
        # Pick a random element from the list and pop it
        random_index = random.randint(0, len(sites_remaining) - 1)
        site_to_visit = sites_remaining.pop(random_index)
        
        # Exponential distribution with mean 180 segs
        wait_time = int(random.expovariate(1 / 180))
        
        command_sequences.append(individual_training_visit_sequence(site_to_visit, next_site_rank, wait_time, cookie_banner_action=cookie_banner_action))
        next_site_rank += 1
        # For now, for testing only 
        # command_sequences.append(individual_training_visit_sequence(site_to_visit, 30))

    return command_sequences