"""Four versioned JSON saves. Atomic replacement keeps the previous save on write failure."""
from copy import deepcopy
from datetime import datetime
import json
import math
import os
from pathlib import Path
import tempfile
from crescendo import MAX_CHARGE, choices_for
from classes import JOBS
from depths import DEN_CHESTS

VERSION = 1
FIELDS = ('x','y','direction','hp','potions','gold','level','xp','party','supplies',
          'analects','materials','materials_sold','gear_inventory','temur_story',
          'in_chamber','boss_cleared','astral_sync','chest_open','outdoors',
          'grass_intro_seen','merren_hint_seen')
BOOL_FIELDS = ('in_chamber','boss_cleared','astral_sync','chest_open','outdoors','grass_intro_seen','merren_hint_seen')
MAP_FIELDS = ('supplies','analects','materials','materials_sold','gear_inventory')
DEPTHS_CHEST_IDS = frozenset(key for key, _ in DEN_CHESTS.values())

class SaveError(ValueError):
    pass

def slot_path(directory, slot):
    if type(slot) is not int or slot not in range(1,5):
        raise SaveError('Choose a slot from 1 to 4.')
    return Path(directory) / f'slot_{slot}.json'

def capture(app):
    state = {key:deepcopy(getattr(app,key)) for key in FIELDS}
    state['field_leader'] = getattr(app, 'field_leader', 'Retri')
    state['route_map'] = getattr(app, 'route_map', False)
    state['cordon_open'] = getattr(app, 'cordon_open', False)
    state['bazaar_bought'] = sorted(app.bazaar_bought)
    state['encounter_steps'] = app.encounters.steps_left
    state['cave_story'] = deepcopy(app.cave_story)
    return state

def validate(state):
    if not isinstance(state,dict) or any(key not in state for key in (*FIELDS,'bazaar_bought','encounter_steps')):
        raise SaveError('Incomplete save data.')
    def count(value): return type(value) is int and 0 <= value <= 1000000000
    for key in ('hp','potions','gold','level','xp','encounter_steps'):
        if not count(state[key]): raise SaveError('Invalid journey statistics.')
    if state['level'] < 1: raise SaveError('Invalid level.')
    for key in BOOL_FIELDS:
        if type(state[key]) is not bool: raise SaveError('Invalid world progress.')
    if (any(type(state.get(key, False)) is not bool for key in ('route_map', 'cordon_open'))
            or state.get('cordon_open', False) and not state.get('route_map', False)):
        raise SaveError('Invalid cordon progress.')
    for key in ('x','y'):
        if type(state[key]) not in (int,float) or not math.isfinite(state[key]) or not 0 <= state[key] < 10000:
            raise SaveError('Invalid save position.')
    if state['direction'] not in ('up','down','left','right') or state['temur_story'] not in ('waiting','joined','declined'):
        raise SaveError('Invalid journey state.')
    for key in MAP_FIELDS:
        if not isinstance(state[key],dict) or any(not isinstance(k,str) or not count(v) for k,v in state[key].items()):
            raise SaveError('Invalid inventory.')
    if not isinstance(state['bazaar_bought'],list) or any(not isinstance(x,str) for x in state['bazaar_bought']):
        raise SaveError('Invalid bazaar progress.')
    party=state['party']
    if not isinstance(party,list) or not 1 <= len(party) <= 2:
        raise SaveError('Invalid party.')
    names=[]
    for person in party:
        if not isinstance(person,dict) or person.get('name') not in ('Retri','Temur'):
            raise SaveError('Invalid party member.')
        names.append(person['name'])
        for key in ('hp','mp','max_hp','max_mp','strength','defense','magic','magic_defense','agility','luck','evasion','accuracy','level','xp','rp'):
            if not count(person.get(key)): raise SaveError('Invalid party statistics.')
        if person['max_hp'] < 1 or person['level'] < 1: raise SaveError('Invalid member level or HP.')
        if person.get('job') not in (None, 'Unbound', 'Cutpurse', 'Saint Warrior', 'Black Reliquary', *JOBS):
            raise SaveError('Invalid class.')
        if not isinstance(person.get('equipment'),dict) or any(not isinstance(k,str) or v is not None and not isinstance(v,str) for k,v in person['equipment'].items()):
            raise SaveError('Invalid equipment.')
        for key in ('researched','observations'):
            if not isinstance(person.get(key),list) or any(not isinstance(x,str) for x in person[key]):
                raise SaveError('Invalid research.')
        ailments=person.get('ailments',{})
        if not isinstance(ailments,dict) or any(key not in ('poison','darkness','silence') or type(value) is not int or value!=-1 for key,value in ailments.items()):
            raise SaveError('Invalid persistent ailments.')
        if 'active' in person and type(person['active']) is not bool: raise SaveError('Invalid party formation.')
        if 'crescendo_charge' in person and (not count(person['crescendo_charge']) or person['crescendo_charge'] > MAX_CHARGE):
            raise SaveError('Invalid Crescendo meter.')
        # Class Crescendo counter (movesets.md). Older saves have none and read as 0.
        if 'crescendo_progress' in person and not count(person['crescendo_progress']):
            raise SaveError('Invalid Crescendo progress.')
        if 'crescendo_choice' in person and person['crescendo_choice'] not in tuple(move.id for move in choices_for(person)):
            raise SaveError('Invalid equipped Crescendo.')
    if names[0]!='Retri' or len(set(names))!=len(names): raise SaveError('Invalid party order.')
    if state.get('field_leader', 'Retri') not in names: raise SaveError('Invalid field leader.')
    if 'cave_story' in state:
        story=state['cave_story']
        if not isinstance(story,dict) or type(story.get('entrance_collapsed')) is not bool or type(story.get('miner_warned')) is not bool:
            raise SaveError('Invalid cave story progress.')
        if not isinstance(story.get('inspected'),list) or any(name not in ('dropped_tools','abandoned_cart','last_lantern','blue_ore_cart','broken_support') for name in story['inspected']):
            raise SaveError('Invalid mining discoveries.')
        flags = ('den_unsealed', 'den_cleared', 'black_stone_attuned', 'black_stone_claimed', 'white_stone_seen')
        if any(type(story.get(flag, False)) is not bool for flag in flags):
            raise SaveError('Invalid den progress.')
        chests = story.get('depths_chests', [])
        if not isinstance(chests, list) or any(not isinstance(chest, str) or chest not in DEPTHS_CHEST_IDS for chest in chests):
            raise SaveError('Invalid Depths treasure progress.')
        if (((story.get('black_stone_attuned') or story.get('black_stone_claimed')) and not story.get('den_cleared')) or
                (story.get('den_cleared') and not story.get('den_unsealed'))):
            raise SaveError('Inconsistent den progress.')
    return state

def read_slot(directory,slot):
    path=slot_path(directory,slot)
    try:
        if path.stat().st_size > 2_000_000: raise SaveError('Save is too large.')
        data=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data,dict) or data.get('version') != VERSION:
            raise SaveError('Unsupported save version.')
        validate(data.get('state'))
        if not isinstance(data.get('saved_at'),str): raise SaveError('Invalid save date.')
        return data
    except FileNotFoundError:
        return None
    except (OSError,ValueError,TypeError,RecursionError) as exc:
        raise SaveError('This save could not be read. Your other slots are unaffected.') from exc

def write_slot(directory,slot,state):
    validate(state)
    path=slot_path(directory,slot);path.parent.mkdir(parents=True,exist_ok=True)
    data={'version':VERSION,'saved_at':datetime.now().astimezone().isoformat(timespec='seconds'),'state':state}
    temp=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,prefix='.saving-',suffix='.tmp',delete=False) as f:
            temp=Path(f.name)
            json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False)
            f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if temp is not None and temp.exists(): temp.unlink()
    return data
