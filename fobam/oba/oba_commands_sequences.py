# sys.path.append("../openwpm")
import random
import sys
from typing import Callable, List
from urllib.parse import urlparse

from bannerclick.config import *
from CMPB_commands import CMPBCommand, CustomBannerInteraction
from openwpm.command_sequence import (
    CommandSequence,
    RecursiveDumpPageSourceCommand,
    ScreenshotFullPageCommand,
)
from openwpm.commands.browser_commands import GetCommand


def control_site_visit_sequence(
    control_site: str,
    next_site_rank: str = 0,
    clean_run: bool = False,
    cookie_banner_action: int = 0,
    banner_results_csv_name = "./datadir/cookie_banner_results.csv",
):
    """Returns a command sequence that makes a clean run for a given control_site"""

    def _control_sites_callback(success: bool, val: str = control_site) -> None:
        print(
            f"{'[CLEAN VISIT]' if clean_run else '[CONTROL VISIT]'} for {val} ran {'SUCCESSFULLY' if success else 'UNSUCCESSFULLY'}"
        )

    control_site_sequence = CommandSequence(
        control_site,
        site_rank=next_site_rank,
        callback=_control_sites_callback,
        reset=clean_run,
    )
    domain = urlparse(control_site).netloc.split(".")[0]
    wait_time = 180 + random.randint(60, 120)
    if cookie_banner_action == 0:
        control_site_sequence.append_command(
            GetCommand(control_site, sleep=wait_time), timeout=wait_time + 120
        )
    else:
        control_site_sequence.append_command(
            CustomBannerInteraction(
                control_site,
                sleep=wait_time,
                timeout=wait_time + 60,
                index=next_site_rank,
                choice=cookie_banner_action,
                result_csv_file_name=banner_results_csv_name
            ),
            timeout=wait_time + 120,
        )
    control_site_sequence.append_command(
        ScreenshotFullPageCommand("_"), timeout=wait_time
    )
    control_site_sequence.append_command(
        RecursiveDumpPageSourceCommand(domain), timeout=wait_time
    )

    return control_site_sequence


def individual_training_visit_sequence(
    training_site: str,
    next_site_rank=None,
    sleep: int = 10,
    creation: bool = False,
    cookie_banner_action: int = 0,
    banner_results_csv_name = "./datadir/cookie_banner_results.csv",
):
    """Visits one training_site"""

    def _training_sites_callback(success: bool, val: str = training_site) -> None:
        print(
            f"{'[CREATION VISIT]' if creation else '[TRAINING VISIT]'} for {val} ran {'SUCCESSFULLY' if success else 'UNSUCCESSFULLY'}"
        )

    training_visit_sequence = CommandSequence(
        training_site,
        callback=_training_sites_callback,
    )

    if creation or cookie_banner_action == 0:
        training_visit_sequence.append_command(
            GetCommand(training_site, sleep=sleep), timeout=sleep + 180
        )
    # TODO: Probar con distintas choices
    else:
        training_visit_sequence.append_command(
            CustomBannerInteraction(
                training_site,
                sleep=sleep,
                index=next_site_rank,
                timeout=sleep + 120,
                choice=cookie_banner_action,
                result_csv_file_name=banner_results_csv_name,
            ),
            timeout=sleep + 180,
        )

    return training_visit_sequence


def training_visits_sequence(
    training_sites: List[str], next_site_rank: int, cookie_banner_action: int = 0
):
    command_sequences = []
    sites_remaining = training_sites.copy()

    while sites_remaining:
        # Pick a random element from the list and pop it
        random_index = random.randint(0, len(sites_remaining) - 1)
        site_to_visit = sites_remaining.pop(random_index)

        # Exponential distribution with mean 180 segs
        wait_time = int(random.expovariate(1 / 180))

        command_sequences.append(
            individual_training_visit_sequence(
                site_to_visit,
                next_site_rank,
                wait_time,
                cookie_banner_action=cookie_banner_action,
            )
        )
        next_site_rank += 1
        # For now, for testing only
        # command_sequences.append(individual_training_visit_sequence(site_to_visit, 30))

    return command_sequences


def get_cookie_banner_visit_sequences(
    training_pages: list,
    control_pages: list = [],
    time_for_user: int = 30,
    banner_results_csv_name="./datadir/cookie_banner_results.csv",
):
    """One by one, visits all of the training pages and control pages."""
    command_sequences = []
    sites_remaining = training_pages.copy()
    sites_remaining.extend(control_pages.copy())
    total_sites = len(sites_remaining)

    while sites_remaining:
        # Pick a random element from the list and pop it
        random_index = random.randint(0, len(sites_remaining) - 1)
        site_to_visit = sites_remaining.pop(random_index)

        def _visit_callback(
            success: bool,
            val: str = site_to_visit,
            site_rank: int = total_sites - len(sites_remaining) + 1,
        ) -> None:
            print(
                f"{f'[REJECT COOKIES VISIT {site_rank}]'} for {val} ran {'SUCCESSFULLY' if success else 'UNSUCCESSFULLY'}"
            )

        next_site_rank = total_sites - len(sites_remaining) + 1
        visit_sequence = CommandSequence(
            site_to_visit,
            # Starts from 1 to total_sites
            site_rank=next_site_rank,
            callback=_visit_callback,
        )

        visit_sequence.append_command(
            CustomBannerInteraction(
                site_to_visit,
                sleep=time_for_user,
                index=next_site_rank,
                timeout=time_for_user + 120,
                choice=2,
                result_csv_file_name=banner_results_csv_name,
            ),
            timeout=time_for_user + 180,
        )

        command_sequences.append(visit_sequence)

    return command_sequences
