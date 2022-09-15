import asyncio
import errno
import json
import re
import sys

import aiohttp
import asyncpraw
import pmaw
import praw
import demoji


async def apply_new_flair(submission, old_flair_regex, link_flair_map):
    match = old_flair_regex.match(demoji.replace(string=submission.link_flair_text, repl=""))
    if match is not None:
        selected_flair = [old_text for old_text, value in match.groupdict().items() if value is not None][-1]
        curr_template = link_flair_map[selected_flair]
        await submission.mod.flair(text=curr_template["text"], flair_template_id=curr_template["id"], css_class=curr_template["css_class"])
    else:
        print(f"Couldn't match submission {submission.id}: {submission.link_flair_text}")


async def apply_new_flairs(configs, submission_names, link_flair_map):
    async with aiohttp.ClientSession() as sess:
        reddit = asyncpraw.Reddit(**configs["reddit"], requestor_kwargs={"session": sess})
        ofr = re.compile(r"|".join(rf"(?P<{old_text}>{old_text})" for old_text in link_flair_map))
        submissions = reddit.info(fullnames=submission_names)
        tasks = [asyncio.create_task(apply_new_flair(submission, ofr, link_flair_map)) async for submission in submissions if submission.link_flair_text is not None]
        await asyncio.gather(*tasks)


if __name__ == '__main__':
    try:
        with open("configs.json") as configs_json:
            cfg = json.load(configs_json)
    except FileNotFoundError:
        print("Couldn't open the configuration file. "
              "Please ensure the file `configs.json` is in the same directory as the executable. "
              "You may need to complete and rename the example file `configs_example.json`.",
              file=sys.stderr)
        sys.exit(errno.ENOENT)

    # BUILD LINK FLAIR MAP
    print("Building link flair mapping...")
    pr = praw.Reddit(**cfg["reddit"])
    subreddit = pr.subreddit(cfg["subreddit"]["name"])
    templates = list(subreddit.flair.link_templates)
    flair_regex = re.compile(r"|".join(rf"(?P<{old_text}>{cfg['link_flair_map'][old_text]})" for old_text in cfg['link_flair_map']))
    lfm = {[old_text for old_text, value in flair_regex.match(template["text"]).groupdict().items() if value is not None][-1]: template for template in templates}
    print(f"{len(lfm)} flairs detected, retrieving all submissions...")

    # QUERY ALL SUBMISSIONS
    ps = pmaw.PushshiftAPI()
    after = cfg["subreddit"]["earliest"] if cfg["subreddit"]["earliest"] is not None else int(subreddit.created_utc)
    submissions_ps = ps.search_submissions(after=after, subreddit=cfg["subreddit"]["name"])
    sn = [f't3_{submission_obj["id"]}' for submission_obj in submissions_ps]
    print(f"{len(sn)} submissions retrieved, applying new flairs...")

    # APPLY FLAIR CHANGE TO ALL SUBMISSIONS
    asyncio.run(apply_new_flairs(cfg, sn, lfm))
    print("Operations complete!")
