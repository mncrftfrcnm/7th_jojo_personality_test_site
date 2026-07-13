#!/usr/bin/env python3
"""Create standalone Game Boy-style personality surveys."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        value = input(f"{prompt}{suffix}: ").strip()
        if value:
            return value
        if default is not None:
            return default
        print("Please enter a value.")


def ask_int(prompt: str, default: int, minimum: int = 1) -> int:
    while True:
        raw = ask(prompt, str(default))
        try:
            value = int(raw)
        except ValueError:
            print("Enter a whole number.")
            continue
        if value < minimum:
            print(f"Enter a number of at least {minimum}.")
            continue
        return value


def choose(prompt: str, choices: list[str], default: int = 0) -> str:
    print(prompt)
    for index, item in enumerate(choices, 1):
        print(f"  {index}. {item}")
    while True:
        raw = ask("Choose", str(default + 1))
        try:
            selected = int(raw) - 1
        except ValueError:
            print("Enter one of the listed numbers.")
            continue
        if 0 <= selected < len(choices):
            return choices[selected]
        print("Enter one of the listed numbers.")


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if not isinstance(config, dict):
        return ["The root value must be an object."]

    meta = config.get("meta")
    if not isinstance(meta, dict):
        errors.append("Missing meta object.")
    else:
        if not meta.get("title"):
            errors.append("meta.title is required.")
        threshold = meta.get("threshold", 5)
        if not isinstance(threshold, int) or threshold < 2:
            errors.append("meta.threshold must be an integer of at least 2.")

    traits = config.get("traits")
    if not isinstance(traits, list) or len(traits) < 2:
        errors.append("traits must contain at least two traits.")
        return errors

    codes = [trait.get("id") for trait in traits if isinstance(trait, dict)]
    known_codes = {code for code in codes if isinstance(code, str) and code}

    if len(known_codes) != len(codes):
        errors.append("Every trait needs a unique, non-empty id.")

    for index, trait in enumerate(traits):
        where = f"traits[{index}]"
        if not isinstance(trait, dict):
            errors.append(f"{where} must be an object.")
            continue

        code = trait.get("id")
        if not isinstance(code, str) or not code.strip():
            errors.append(f"{where}.id is required.")
        if not trait.get("name"):
            errors.append(f"{where}.name is required.")

        questions = trait.get("questions")
        if not isinstance(questions, list) or not questions:
            errors.append(f"{where}.questions must contain at least one question.")
            continue

        for q_index, question in enumerate(questions):
            q_where = f"{where}.questions[{q_index}]"
            if not isinstance(question, dict):
                errors.append(f"{q_where} must be an object.")
                continue
            if not question.get("text"):
                errors.append(f"{q_where}.text is required.")
            options = question.get("options")
            if not isinstance(options, list) or len(options) < 2:
                errors.append(f"{q_where}.options must contain at least two choices.")
                continue
            for o_index, option in enumerate(options):
                o_where = f"{q_where}.options[{o_index}]"
                if not isinstance(option, dict):
                    errors.append(f"{o_where} must be an object.")
                    continue
                if not option.get("text"):
                    errors.append(f"{o_where}.text is required.")
                if option.get("trait") not in known_codes:
                    errors.append(f"{o_where}.trait must reference a known trait.")
                points = option.get("points", 1)
                if not isinstance(points, int) or points < 1:
                    errors.append(f"{o_where}.points must be a positive integer.")

        neighbors = trait.get("neighbors", [])
        if not isinstance(neighbors, list):
            errors.append(f"{where}.neighbors must be a list.")
        else:
            for neighbor in neighbors:
                if neighbor not in known_codes:
                    errors.append(f"{where}.neighbors contains unknown trait {neighbor!r}.")

    opening = config.get("opening")
    if not isinstance(opening, dict):
        errors.append("Missing opening object.")
    else:
        mode = opening.get("mode")
        if mode not in {"direct", "matrix"}:
            errors.append("opening.mode must be direct or matrix.")
        questions = opening.get("questions")
        if not isinstance(questions, list) or not questions:
            errors.append("opening.questions must contain at least one question.")
        else:
            for q_index, question in enumerate(questions):
                if not isinstance(question, dict):
                    errors.append(f"opening.questions[{q_index}] must be an object.")
                    continue
                options = question.get("options", [])
                if not question.get("text"):
                    errors.append(f"opening.questions[{q_index}].text is required.")
                if not isinstance(options, list) or len(options) < 2:
                    errors.append(f"opening.questions[{q_index}].options needs at least two choices.")

            if mode == "direct" and questions:
                for o_index, option in enumerate(questions[-1].get("options", [])):
                    if option.get("trait") not in known_codes:
                        errors.append(
                            f"opening.questions[-1].options[{o_index}].trait must reference a known trait."
                        )
            elif mode == "matrix":
                if len(questions) != 2:
                    errors.append("Matrix mode requires exactly two opening questions.")
                routes = opening.get("routes")
                if not isinstance(routes, dict):
                    errors.append("Matrix mode requires opening.routes.")
                elif len(questions) == 2:
                    expected = len(questions[0].get("options", [])) * len(questions[1].get("options", []))
                    if len(routes) != expected:
                        errors.append(f"opening.routes has {len(routes)} entries; {expected} are required.")
                    for key, value in routes.items():
                        if value not in known_codes:
                            errors.append(f"opening.routes[{key!r}] references unknown trait {value!r}.")

    results = config.get("results")
    if not isinstance(results, list) or not results:
        errors.append("results must contain at least one result.")
    else:
        for index, result in enumerate(results):
            where = f"results[{index}]"
            if not isinstance(result, dict):
                errors.append(f"{where} must be an object.")
                continue
            if result.get("main_trait") not in known_codes:
                errors.append(f"{where}.main_trait must reference a known trait.")
            sub = result.get("sub_trait")
            if sub is not None and sub not in known_codes:
                errors.append(f"{where}.sub_trait must reference a known trait.")
            if not result.get("name"):
                errors.append(f"{where}.name is required.")

    return errors


def option_wizard(codes: list[str], label: str) -> dict[str, Any]:
    print(f"\n{label}")
    return {
        "text": ask("Choice text"),
        "trait": choose("Which trait receives points?", codes),
        "points": ask_int("Points added", 1),
        "karma": ask_int("Bonus added", 0, minimum=0),
    }


def question_wizard(codes: list[str], label: str) -> dict[str, Any]:
    print(f"\n{label}")
    text = ask("Question")
    count = ask_int("Number of choices", 2, minimum=2)
    options = [option_wizard(codes, f"Choice {index + 1}") for index in range(count)]
    return {"text": text, "options": options}


def result_wizard(main_trait: str, sub_trait: str | None = None) -> dict[str, Any]:
    pair = f"{main_trait}/{sub_trait}" if sub_trait else main_trait
    print(f"\nResult for {pair}")
    result: dict[str, Any] = {
        "main_trait": main_trait,
        "name": ask("Result name"),
        "description": ask("Description", ""),
        "image": ask("Image URL or relative path", ""),
        "url": ask("More information URL", ""),
    }
    if sub_trait:
        result["sub_trait"] = sub_trait
    return result


def run_wizard(output: Path) -> None:
    print("\nGame Boy Survey Builder\n")

    title = ask("Survey title", "Personality Evaluation")
    subtitle = ask("Subtitle", "Discover your result")
    threshold = ask_int("Winning trait score", 5, minimum=2)
    random_min = ask_int("Minimum starting points", 1)
    random_max = ask_int("Maximum starting points", 3)
    if random_max < random_min:
        random_min, random_max = random_max, random_min

    trait_count = ask_int("Number of traits", 3, minimum=2)
    traits: list[dict[str, Any]] = []
    used: set[str] = set()

    for index in range(trait_count):
        print(f"\nTrait {index + 1}")
        default_code = chr(65 + index) if index < 26 else f"T{index + 1}"
        while True:
            code = ask("Trait id", default_code).strip()
            if code not in used:
                break
            print("That id is already in use.")
        used.add(code)
        traits.append({"id": code, "name": ask("Trait name"), "neighbors": [], "questions": []})

    codes = [trait["id"] for trait in traits]

    print("\nSub-trait neighbors")
    print("Enter comma-separated trait ids. Leave blank to consider every other trait.")
    for trait in traits:
        raw = ask(f"Neighbors for {trait['id']}", "")
        if raw:
            neighbors = [item.strip() for item in raw.split(",") if item.strip()]
            trait["neighbors"] = [item for item in neighbors if item in codes and item != trait["id"]]
        else:
            trait["neighbors"] = [item for item in codes if item != trait["id"]]

    start_choice = choose(
        "\nHow should the starting trait be selected?",
        [
            "direct: the final opening answer points to a trait",
            "matrix: the combination of two opening answers points to a trait",
        ],
    )
    start_mode = start_choice.split(":", 1)[0]
    opening: dict[str, Any] = {"mode": start_mode, "questions": []}

    if start_mode == "direct":
        opening_count = ask_int("Number of opening questions", 1)
        for q_index in range(opening_count):
            print(f"\nOpening question {q_index + 1}")
            text = ask("Question")
            choice_count = ask_int("Number of choices", 3, minimum=2)
            options = []
            for o_index in range(choice_count):
                print(f"\nChoice {o_index + 1}")
                option: dict[str, Any] = {"text": ask("Choice text")}
                if q_index == opening_count - 1:
                    option["trait"] = choose("Starting trait", codes)
                options.append(option)
            opening["questions"].append({"text": text, "options": options})
    else:
        for q_index in range(2):
            print(f"\nOpening question {q_index + 1}")
            text = ask("Question")
            choice_count = ask_int("Number of choices", 3, minimum=2)
            options = [{"text": ask(f"Choice {index + 1}")} for index in range(choice_count)]
            opening["questions"].append({"text": text, "options": options})

        routes: dict[str, str] = {}
        first_options = opening["questions"][0]["options"]
        second_options = opening["questions"][1]["options"]
        print("\nSet a starting trait for every answer combination.")
        for first_index, first in enumerate(first_options):
            for second_index, second in enumerate(second_options):
                key = f"{first_index},{second_index}"
                routes[key] = choose(f"{first['text']} + {second['text']}", codes)
        opening["routes"] = routes

    print("\nTrait questions")
    print("The final question is reused if a trait has fewer questions than score levels.")
    default_questions = max(1, threshold - 1)
    for trait in traits:
        count = ask_int(f"Questions for {trait['id']} ({trait['name']})", default_questions)
        trait["questions"] = [
            question_wizard(codes, f"{trait['id']} question {index + 1}")
            for index in range(count)
        ]

    result_mode = choose(
        "\nHow should results be assigned?",
        ["main trait only", "main trait and sub-trait pair"],
    )

    results: list[dict[str, Any]] = []
    if result_mode == "main trait only":
        for code in codes:
            results.append(result_wizard(code))
    else:
        for trait in traits:
            for neighbor in trait["neighbors"]:
                results.append(result_wizard(trait["id"], neighbor))

    config = {
        "meta": {
            "title": title,
            "subtitle": subtitle,
            "threshold": threshold,
            "random_start_points": [random_min, random_max],
            "sound": True,
        },
        "opening": opening,
        "traits": traits,
        "results": results,
    }

    output.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved {output}")
    print(f"Build it with:\n  python {Path(sys.argv[0]).name} build {output} -o index.html")


def example_config() -> dict[str, Any]:
    return {
        "meta": {
            "title": "Element Evaluation",
            "subtitle": "Discover your affinity",
            "threshold": 5,
            "random_start_points": [1, 3],
            "sound": True,
        },
        "opening": {
            "mode": "direct",
            "questions": [
                {
                    "text": "A storm is approaching. What do you do?",
                    "options": [
                        {"text": "Stand my ground", "trait": "FIRE"},
                        {"text": "Find a safe route", "trait": "WATER"},
                        {"text": "Climb somewhere high", "trait": "AIR"},
                    ],
                }
            ],
        },
        "traits": [
            {
                "id": "FIRE",
                "name": "Bold",
                "neighbors": ["AIR", "WATER"],
                "questions": [
                    {
                        "text": "Do you act before others have decided?",
                        "options": [
                            {"text": "Yes", "trait": "FIRE", "points": 1, "karma": 0},
                            {"text": "No", "trait": "WATER", "points": 1, "karma": 0},
                        ],
                    },
                    {
                        "text": "Would you challenge a stronger opponent?",
                        "options": [
                            {"text": "Yes", "trait": "FIRE", "points": 1, "karma": 1},
                            {"text": "No", "trait": "AIR", "points": 1, "karma": 0},
                        ],
                    },
                ],
            },
            {
                "id": "WATER",
                "name": "Adaptable",
                "neighbors": ["FIRE", "AIR"],
                "questions": [
                    {
                        "text": "Do you change plans when circumstances change?",
                        "options": [
                            {"text": "Yes", "trait": "WATER", "points": 1, "karma": 0},
                            {"text": "No", "trait": "FIRE", "points": 1, "karma": 0},
                        ],
                    },
                    {
                        "text": "Do you prefer listening before speaking?",
                        "options": [
                            {"text": "Yes", "trait": "WATER", "points": 1, "karma": 0},
                            {"text": "No", "trait": "AIR", "points": 1, "karma": 0},
                        ],
                    },
                ],
            },
            {
                "id": "AIR",
                "name": "Curious",
                "neighbors": ["WATER", "FIRE"],
                "questions": [
                    {
                        "text": "Do unfamiliar places excite you?",
                        "options": [
                            {"text": "Yes", "trait": "AIR", "points": 1, "karma": 0},
                            {"text": "No", "trait": "WATER", "points": 1, "karma": 0},
                        ],
                    },
                    {
                        "text": "Would you rather improvise than follow a plan?",
                        "options": [
                            {"text": "Yes", "trait": "AIR", "points": 1, "karma": 0},
                            {"text": "No", "trait": "FIRE", "points": 1, "karma": 0},
                        ],
                    },
                ],
            },
        ],
        "results": [
            {
                "main_trait": "FIRE",
                "name": "Crimson Spark",
                "description": "A direct and forceful result driven by courage.",
                "image": "",
                "url": "",
            },
            {
                "main_trait": "WATER",
                "name": "Silent Current",
                "description": "A flexible result that turns obstacles into new paths.",
                "image": "",
                "url": "",
            },
            {
                "main_trait": "AIR",
                "name": "Open Horizon",
                "description": "A curious result that values freedom and discovery.",
                "image": "",
                "url": "",
            },
        ],
    }


CSS = r'''
:root{--shell:#c8c8bd;--ink:#0f380f;--mid:#306230;--light:#8bac0f;--screen:#9bbc0f;--button:#8a174f}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:16px 10px;background:radial-gradient(circle at 50% 15%,#343842,#17191e 62%,#0c0d10);font-family:"Courier New",monospace}
button,a{font:inherit}
.gameboy{width:min(440px,96vw);padding:24px 22px 20px;border:2px solid #e5e5dc;border-right-color:#777971;border-bottom-color:#676961;border-radius:18px 18px 62px 18px;background:var(--shell);box-shadow:0 18px 50px #0009,inset 4px 4px 0 #fff6,inset -4px -4px 0 #73756e66;user-select:none}
.screen-frame{padding:18px 20px 24px;border-radius:12px 12px 38px 12px;background:#555866;box-shadow:inset 3px 3px 0 #30323a,inset -2px -2px 0 #7d8090}
.screen-label{display:flex;align-items:center;gap:8px;margin-bottom:8px;color:#c7c9d0;font:700 9px/1 Arial,sans-serif;letter-spacing:1.4px;text-transform:uppercase}
.screen-label:before,.screen-label:after{content:"";height:2px;flex:1;background:linear-gradient(90deg,#b3195b,#303a8f)}
.screen{position:relative;min-height:430px;overflow:hidden;border:4px solid #22261e;border-radius:4px;background:var(--screen);color:var(--ink);box-shadow:inset 0 0 0 4px #77920c,inset 0 0 28px #46600066}
.screen:after{content:"";pointer-events:none;position:absolute;inset:0;background:repeating-linear-gradient(to bottom,transparent 0,transparent 3px,#0f380f12 4px);mix-blend-mode:multiply}
.screen-inner{position:relative;z-index:1;height:100%;padding:14px;display:flex;flex-direction:column}
.hud{display:flex;justify-content:space-between;gap:8px;padding-bottom:7px;border-bottom:2px solid var(--ink);font-size:11px;font-weight:700}
.page{min-height:0;flex:1;display:flex;flex-direction:column;justify-content:center;overflow:auto;padding:8px 0}
.eyebrow{margin:0 0 8px;color:var(--mid);font-size:11px;font-weight:700;text-transform:uppercase}
h1,h2,p{margin-top:0}h1{margin-bottom:12px;font-size:clamp(27px,8vw,40px);line-height:.95;letter-spacing:-2px;text-transform:uppercase;text-shadow:3px 3px 0 var(--light)}h2{margin-bottom:12px;font-size:17px;line-height:1.18;text-transform:uppercase}.small{color:var(--mid);font-size:11px;line-height:1.35}
.menu{display:grid;gap:7px;margin-top:10px}.choice{width:100%;min-height:34px;padding:6px 8px 6px 22px;border:0;background:transparent;color:var(--ink);text-align:left;font-weight:700;line-height:1.2;cursor:pointer;position:relative}.choice.selected{background:#8bac0f80;outline:2px solid var(--ink)}.choice.selected:before{content:"▶";position:absolute;left:6px;top:50%;transform:translateY(-50%);font-size:10px}
.result-name{margin:2px 0 8px;font-size:clamp(24px,8vw,34px);line-height:.95;letter-spacing:-1.5px;text-transform:uppercase}.result-image{display:block;width:120px;height:120px;margin:8px auto;object-fit:contain;border:2px solid var(--ink);background:var(--light)}.description{font-size:11px;line-height:1.35;white-space:pre-wrap}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:4px 8px;margin:10px 0;font-size:10px;font-weight:700}.result-link{display:inline-block;margin-top:8px;padding:7px 9px;border:2px solid var(--ink);color:var(--ink);background:var(--light);font-weight:700;text-decoration:none;text-transform:uppercase}.result-link:hover,.result-link:focus{color:var(--screen);background:var(--ink)}
.hint{min-height:18px;padding-top:7px;border-top:2px solid var(--ink);color:var(--mid);font-size:10px;text-align:center;text-transform:uppercase}.brand{margin:14px 0 6px;color:#313343;font-family:Arial,sans-serif;font-size:18px;font-style:italic;font-weight:900;letter-spacing:-1px}.brand span{color:#303a8f;font-size:11px;letter-spacing:1px}
.controls{display:flex;align-items:center;justify-content:space-between;min-height:145px;padding:10px 14px 0}.dpad{width:112px;height:112px;position:relative}.dpad button{position:absolute;width:38px;height:38px;border:0;background:#25272a;color:#85878a;cursor:pointer;box-shadow:inset 2px 2px 0 #4d4f53,inset -3px -3px 0 #101113,0 3px 0 #74766f}.up{left:37px;top:0}.left{left:0;top:37px}.right{right:0;top:37px}.down{left:37px;bottom:0}.dpad:after{content:"";position:absolute;left:37px;top:37px;width:38px;height:38px;background:#25272a;box-shadow:inset 2px 2px 0 #4d4f53,inset -3px -3px 0 #101113}.action-buttons{display:flex;gap:14px;transform:rotate(-18deg)}.action{width:56px;height:56px;border:0;border-radius:50%;background:var(--button);color:#e6a9c7;font-weight:900;cursor:pointer;box-shadow:inset 3px 3px 0 #b8467a,inset -4px -4px 0 #52102f,0 5px 0 #85877f}.system-buttons{display:flex;justify-content:center;gap:22px;margin-top:-10px;transform:rotate(-18deg)}.system-button{width:62px;height:14px;border:0;border-radius:999px;background:#777971;color:#4e504b;font-size:8px;font-weight:700;line-height:30px;cursor:pointer;box-shadow:inset 2px 2px 0 #999b94,inset -2px -2px 0 #555750}.blink{animation:blink 1s steps(2,end) infinite}@keyframes blink{50%{opacity:0}}@media(max-width:420px){body{padding:8px}.gameboy{padding:18px 14px 16px}.screen-frame{padding:14px 14px 20px}.screen{min-height:410px}.controls{min-height:135px;padding-inline:6px}.dpad{transform:scale(.88)}.action-buttons{transform:rotate(-18deg) scale(.9)}}
'''


JS = r'''
const page=document.querySelector("#page"),statusEl=document.querySelector("#status"),hint=document.querySelector("#hint");
const meta=SURVEY.meta,traits=Object.fromEntries(SURVEY.traits.map(trait=>[trait.id,trait]));
let cursor=0,mode="title",openingIndex=0,openingAnswers=[],scores=blankScores(),karma=0,currentTrait="",currentQuestion=null,questionCount=0,soundOn=meta.sound!==false;
function blankScores(){return Object.fromEntries(SURVEY.traits.map(trait=>[trait.id,0]))}
function randomStartPoints(){const range=meta.random_start_points||[1,1],min=Math.min(range[0],range[1]),max=Math.max(range[0],range[1]);return Math.floor(Math.random()*(max-min+1))+min}
function reset(){cursor=0;mode="title";openingIndex=0;openingAnswers=[];scores=blankScores();karma=0;currentTrait="";currentQuestion=null;questionCount=0;render()}
function startQuiz(){cursor=0;mode="opening";openingIndex=0;openingAnswers=[];scores=blankScores();karma=0;questionCount=0;beep(520,.06);render()}
function selectChoice(){
  if(mode==="title"){startQuiz();return}
  if(mode==="opening"){
    openingAnswers.push(cursor);const last=openingIndex===SURVEY.opening.questions.length-1;
    if(!last){openingIndex+=1;cursor=0;beep(600,.04);render();return}
    if(SURVEY.opening.mode==="matrix")currentTrait=SURVEY.opening.routes[openingAnswers.join(",")];
    else currentTrait=SURVEY.opening.questions[openingIndex].options[cursor].trait;
    scores[currentTrait]=randomStartPoints();currentQuestion=questionFor(currentTrait);mode="question";cursor=0;beep(740,.08);render();return
  }
  if(mode==="question"){
    const option=currentQuestion.options[cursor];karma+=option.karma||0;scores[option.trait]+=(option.points||1);currentTrait=option.trait;questionCount+=1;
    if(scores[currentTrait]>=meta.threshold){showResult(currentTrait);return}
    currentQuestion=questionFor(currentTrait);cursor=0;beep(option.karma?880:660,option.karma?.12:.05);render();return
  }
  if(mode==="result")startQuiz()
}
function questionFor(traitId){const questions=traits[traitId].questions,index=Math.max(0,Math.min(scores[traitId]-1,questions.length-1));return questions[index]}
function pickSubTrait(mainTrait){const listed=traits[mainTrait].neighbors||[],candidates=listed.length?listed:Object.keys(traits).filter(id=>id!==mainTrait),best=Math.max(...candidates.map(id=>scores[id])),tied=candidates.filter(id=>scores[id]===best),preferred=meta.tie_breaker_by_main?.[mainTrait];if(preferred&&tied.includes(preferred))return preferred;return tied[tied.length-1]}
function findResult(mainTrait,subTrait){return SURVEY.results.find(result=>result.main_trait===mainTrait&&result.sub_trait===subTrait)||SURVEY.results.find(result=>result.main_trait===mainTrait&&!result.sub_trait)||{name:traits[mainTrait].name,description:"",image:"",url:""}}
function showResult(mainTrait){
  mode="result";const subTrait=pickSubTrait(mainTrait),result=findResult(mainTrait,subTrait),image=result.image?`<img class="result-image" src="${escapeAttr(result.image)}" alt="${escapeAttr(result.name)}">`:"",link=result.url?`<a class="result-link" href="${escapeAttr(result.url)}" target="_blank" rel="noreferrer">More Info</a>`:"";
  statusEl.textContent="COMPLETE";hint.textContent="A/START: RETAKE";
  page.innerHTML=`<div><p class="eyebrow">Evaluation complete</p><h2>Your result is</h2><div class="result-name">${escapeHtml(result.name)}</div><p class="small">${escapeHtml(mainTrait)} · ${escapeHtml(traits[mainTrait].name)}<br>Sub-trait ${escapeHtml(subTrait)} · Bonus ${karma}</p>${image}<p class="description">${escapeHtml(result.description||"")}</p><div class="stats">${Object.entries(scores).map(([id,value])=>`<span>${escapeHtml(id)}:${value}</span>`).join("")}</div>${link}</div>`;
  beep(440,.08);setTimeout(()=>beep(660,.08),90);setTimeout(()=>beep(880,.14),180)
}
function move(amount){const count=choiceCount();if(count<2)return;cursor=(cursor+amount+count)%count;beep(330,.025);render()}
function choiceCount(){if(mode==="opening")return SURVEY.opening.questions[openingIndex].options.length;if(mode==="question")return currentQuestion.options.length;return 1}
function render(){
  document.title=meta.title;
  if(mode==="title"){statusEl.textContent="READY";hint.textContent="PRESS START · ENTER · Z";page.innerHTML=`<div><p class="eyebrow">${escapeHtml(meta.subtitle||"")}</p><h1>${escapeHtml(meta.title)}</h1><button class="choice selected blink" data-choice="0">START</button></div>`;wireChoices();return}
  if(mode==="opening"){const item=SURVEY.opening.questions[openingIndex];statusEl.textContent=`INTRO ${openingIndex+1}/${SURVEY.opening.questions.length}`;hint.textContent="ARROWS: MOVE · A/Z/ENTER: SELECT";page.innerHTML=`<div><p class="eyebrow">Opening question ${openingIndex+1}</p><h2>${escapeHtml(item.text)}</h2><div class="menu">${item.options.map((option,index)=>choiceButton(option.text,index)).join("")}</div></div>`;wireChoices();return}
  if(mode==="question"){statusEl.textContent=`${currentTrait}:${scores[currentTrait]}/${meta.threshold} B:${karma}`;hint.textContent=`Q${questionCount+1} · ARROWS + A/Z/ENTER`;page.innerHTML=`<div><p class="eyebrow">${escapeHtml(currentTrait)} · ${escapeHtml(traits[currentTrait].name)} · Level ${scores[currentTrait]}</p><h2>${escapeHtml(currentQuestion.text)}</h2><div class="menu">${currentQuestion.options.map((option,index)=>choiceButton(option.text,index)).join("")}</div></div>`;wireChoices()}
}
function choiceButton(label,index){return `<button class="choice${index===cursor?" selected":""}" data-choice="${index}">${escapeHtml(label)}</button>`}
function wireChoices(){document.querySelectorAll("[data-choice]").forEach(button=>button.addEventListener("click",()=>{cursor=Number(button.dataset.choice);selectChoice()}))}
function escapeHtml(value){return String(value).replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[char]))}
function escapeAttr(value){return escapeHtml(value)}
function toggleSound(){soundOn=!soundOn;hint.textContent=soundOn?"SOUND ON":"SOUND OFF";if(soundOn)beep(520,.05)}
function beep(frequency,duration){if(!soundOn)return;const AudioContext=window.AudioContext||window.webkitAudioContext;if(!AudioContext)return;const audio=beep.context||(beep.context=new AudioContext()),oscillator=audio.createOscillator(),gain=audio.createGain(),now=audio.currentTime;oscillator.type="square";oscillator.frequency.setValueAtTime(frequency,now);gain.gain.setValueAtTime(.035,now);gain.gain.exponentialRampToValueAtTime(.0001,now+duration);oscillator.connect(gain);gain.connect(audio.destination);oscillator.start(now);oscillator.stop(now+duration)}
document.addEventListener("keydown",event=>{const key=event.key.toLowerCase();if(["arrowup","arrowleft"].includes(key)){event.preventDefault();move(-1)}if(["arrowdown","arrowright"].includes(key)){event.preventDefault();move(1)}if(["enter"," ","z"].includes(key)){event.preventDefault();selectChoice()}if(key==="x"||key==="m")toggleSound();if(key==="r")reset()});
document.querySelectorAll("[data-move]").forEach(button=>button.addEventListener("click",()=>move(Number(button.dataset.move))));document.querySelector("#buttonA").addEventListener("click",selectChoice);document.querySelector("#buttonB").addEventListener("click",toggleSound);document.querySelector("#startButton").addEventListener("click",selectChoice);document.querySelector("#restartButton").addEventListener("click",reset);render();
'''


def build_html(config: dict[str, Any]) -> str:
    title = html.escape(config["meta"]["title"])
    data = json.dumps(config, ensure_ascii=False).replace("</", "<\\/")
    return f'''<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{CSS}</style></head>
<body>
<main class="gameboy">
  <section class="screen-frame"><div class="screen-label">Dot matrix with stereo sound</div><div class="screen"><div class="screen-inner"><div class="hud"><span>SURVEY</span><span id="status">READY</span></div><div class="page" id="page" aria-live="polite"></div><div class="hint" id="hint">ARROWS: MOVE · Z/ENTER: SELECT</div></div></div></section>
  <div class="brand">PERSONALITY <span>SYSTEM</span></div>
  <section class="controls"><div class="dpad"><button class="up" data-move="-1" aria-label="Move up">▲</button><button class="left" data-move="-1" aria-label="Move left">◀</button><button class="right" data-move="1" aria-label="Move right">▶</button><button class="down" data-move="1" aria-label="Move down">▼</button></div><div class="action-buttons"><button class="action" id="buttonB">B</button><button class="action" id="buttonA">A</button></div></section>
  <div class="system-buttons"><button class="system-button" id="restartButton">SELECT</button><button class="system-button" id="startButton">START</button></div>
</main>
<script>const SURVEY={data};\n{JS}</script>
</body></html>'''


def load_config(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"File not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}")


def command_build(config_path: Path, output: Path) -> None:
    config = load_config(config_path)
    errors = validate_config(config)
    if errors:
        print("The survey config has errors:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        raise SystemExit(1)
    output.write_text(build_html(config), encoding="utf-8")
    print(f"Wrote {output}")


def command_validate(config_path: Path) -> None:
    config = load_config(config_path)
    errors = validate_config(config)
    if errors:
        print("Invalid survey:")
        for error in errors:
            print(f"  - {error}")
        raise SystemExit(1)
    print("Survey config is valid.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create standalone Game Boy-style surveys.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    wizard_parser = subparsers.add_parser("wizard", help="Create a survey config interactively.")
    wizard_parser.add_argument("output", type=Path, help="JSON config to create.")

    build_parser = subparsers.add_parser("build", help="Build a standalone HTML survey.")
    build_parser.add_argument("config", type=Path, help="Survey JSON config.")
    build_parser.add_argument("-o", "--output", type=Path, default=Path("index.html"))

    example_parser = subparsers.add_parser("example", help="Write an editable example config.")
    example_parser.add_argument("output", type=Path, default=Path("example_survey.json"), nargs="?")

    validate_parser = subparsers.add_parser("validate", help="Check a survey config.")
    validate_parser.add_argument("config", type=Path)

    args = parser.parse_args()
    if args.command == "wizard":
        run_wizard(args.output)
    elif args.command == "build":
        command_build(args.config, args.output)
    elif args.command == "example":
        args.output.write_text(json.dumps(example_config(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {args.output}")
    elif args.command == "validate":
        command_validate(args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
