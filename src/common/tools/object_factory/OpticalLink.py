# Copyright 2022-2026 ETSI SDG TeraFlowSDN (TFS) (https://tfs.etsi.org/)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import copy

def convert_to_dict(single_val: int, start_point: int = 0, width: int = None) -> dict:
    slot = dict()
    sliced_num = bin(single_val)[2:]
    if width is not None:
        sliced_num = sliced_num.zfill(width)
    for i, bit in enumerate(sliced_num):
        slot[str(start_point + i)] = int(bit)
    return slot

def correct_slot(dic: dict, width: int = None) -> dict:
    corrected = copy.deepcopy(dic)
    if len(corrected) == 0:
        return corrected

    normalized = {int(key): int(value) for key, value in corrected.items()}
    max_slot = max(normalized.keys())
    max_range = width if width is not None else max_slot + 1

    for slot_idx in range(max_range):
        normalized.setdefault(slot_idx, 1)

    return {str(key): normalized[key] for key in sorted(normalized.keys())}


## To be deleted , needed now for development purpose ## 

def order_list (lst:list[tuple])->list:
    if (len(lst)<=1):
        return lst
    else :
        pivot,bit_val =lst[0]
        lst_smaller = []
        lst_greater = []
        for element in lst[1:]:
            key,val=element
            if (key <= pivot):
                lst_smaller.append(element)
            else :
                lst_greater.append(element)
        return order_list(lst_smaller) + [(pivot,bit_val)] + order_list(lst_greater)

def list_to_dict (lst:list[tuple[int,int]])->dict:
    dct = dict()
    for ele in lst :
        key,value = ele
        dct[str(key)]=value
    return dct

def order_dict (dct:dict)->dict:
    lst = list()
    for key,value in sorted(dct.items()):
        lst.append((int(key),value))
    ordered_lst= order_list(lst)
    if (len(ordered_lst)>0):
        return list_to_dict (ordered_lst)

def order_dict_v1 (dct:dict)->dict:
    lst = list()
    for key,value in dct.items():
        lst.append((int(key),value))
    ordered_lst= order_list(lst)
    if (len(ordered_lst)>0):
        return list_to_dict (ordered_lst)
