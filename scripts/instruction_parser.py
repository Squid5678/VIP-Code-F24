
import os
import subprocess
import uuid
from collections import defaultdict
import json
import requests

from std_msgs.msg import String, Bool
from std_srvs.srv import Trigger

# NOTE: Set this variable to spoof LLM output.
#SPOOF_LLM = None
SPOOF_LLM = "(:goal\n (contain bottle_0 sink_0) )"

class InstructionParser(object):
    def __init__(self):
        self.dict_pddlid_graphid = {}

        # set rate as 10Hz
        self.rate = 10
        self.LLM_UPPER_LIMIT = 5 # number of times for LLM to re-parse if PDDL fails
        self.prompt_template = ""
        self.current_file_path = os.path.dirname(os.path.abspath(__file__))
        self.domain_file_path = os.path.join(self.current_file_path, '../config/pick_n_place_nav_domain_cost.pddl')
        self.problem_file_path = os.path.join(self.current_file_path, '../config/pick_n_place_nav_problem.pddl')
        self.solution_path = os.path.join(self.current_file_path, '../config/result.txt')
        self.initial_pddl_problem = ""

        # wait for the environment manager finishes modeling
        # the environment and parse it into PDDL initial specification
        self.initial_pddl_problem = self.load_pddl_inital_problem()


        # pre-load prompt template
        try:
            with open(os.path.join(self.current_file_path, '../config/prompt_template_v6.txt'), 'r') as f: # v5: just take domain definition and instruction 
                self.prompt_template = f.read()
        except FileNotFoundError:
            print('Template file of prompt doesn not exist!')
        
    
    def instruction_callback(self):
        instruction = data.data
        print("Receive the human instruction: {}".format(instruction))

        # trim initial state based on instruction to avoid max token limit
        revised_initial_pddl_problem = self.revise_trim_pddl_problem(self.initial_pddl_problem, instruction)

        # write domain definition in prompt
        domain = self.load_domain_definition()

        # fill domain definition into the prompt 
        prompt_d = self.prompt_template.replace('domain_definition', domain)
        # fill initial pddl problem definition into the prompt
        prompt_d_i = prompt_d.replace('test_problem_definition', revised_initial_pddl_problem)
        # fill instruction into the prompt
        prompt_d_i_i = prompt_d_i.replace('test_human_instruction', instruction)
        #print(prompt_d_i_i)
        #input()

        pddl_result = False
        cnt = 0
        while not pddl_result and cnt < self.LLM_UPPER_LIMIT:
            # call ollama to interpret human instruction
            if SPOOF_LLM:
                llm_output = SPOOF_LLM
            else:
                api_url = "http://localhost:11434/api/generate"

                headers = {
                    "Content-Type": "application/json"
                }

                data = {
                    "model": "llama3.2",
                    "prompt": prompt_d_i_i,
                    "stream": False
                }

                response = requests.post(api_url, headers=headers, data=json.dumps(data))

                if response.status_code == 200:
                    response_text = response.text
                    data = json.loads(response_text)
                    llm_output = data["response"]
                else:
                    print("Unable to get a response from OLlama API")

                # output = replicate.run( 
                #     "replicate/llama-2-70b-chat:02e509c789964a7ea8736978a43525956ef40397be9033abf9fd2badfe68c9e3", 
                #     input={
                #         "prompt": prompt_d_i_i,
                #         "max_new_tokens": 500,
                #         "min_new_tokens": -1,
                #     } 
                # )
                # llm_output = ''.join(str(item) for item in output)

            # process raw LLM output
            revised_llm_output, nonexist_objs = self.revise_raw_llm_output(llm_output)
            print("Output from LLM: {}".format(revised_llm_output))

            # reconstruct the problem
            pddl_problem = self.reconstruct_pddl_problem_definition(self.initial_pddl_problem, revised_llm_output, nonexist_objs)

            # write the problem
            self.write_pddl_problem(pddl_problem)

            # call PDDL solver
            pddl_result = self.pddl_solving()

            # increment the counter
            cnt += 1
        
        
    def parse_name_from_id(self, node_id):
        return node_id.rsplit('_', 2)[0]

    def check_object_in_instruction(self, ins, obj):
        return obj.lower() in ins.lower()

    def revise_trim_pddl_problem(self, problem_def, instruction):
        '''
        Replace node_id which was construct by id by simpler and shorter one
        and trim redundant objects
        '''
        obj_set = defaultdict(int)

        problem_list = problem_def.split('\n')
        for i, s in enumerate(problem_list):
            if " - object" in s:
                node_id = s.split("- object")[0].strip()
                node_name = self.parse_name_from_id(node_id)

                new_id = node_name + "_" + str(obj_set[node_name])
                self.dict_pddlid_graphid[new_id] = node_id
                obj_set[node_name] = obj_set[node_name] + 1
            elif "    (:init " in s:
                break
        
        for new_id, old_id in self.dict_pddlid_graphid.items():
            problem_def = problem_def.replace(old_id, new_id)
        
        problem_list = problem_def.split('\n')
        obj_involved = set()
        for s in problem_list:
            if 'close' in s:
                s_list = s.split()
                obj1_id = s_list[1]
                obj2_id = s_list[2].split(")")[0]

                obj1_name = self.parse_name_from_id(obj1_id)
                obj2_name = self.parse_name_from_id(obj2_id)

                if self.check_object_in_instruction(instruction, obj1_name) or self.check_object_in_instruction(instruction, obj2_name):
                    obj_involved.add(obj1_id)
                    obj_involved.add(obj2_id)
            elif " - object" in s:
                obj_id = s.split("- object")[0].strip()
                obj_name = self.parse_name_from_id(obj_id)

                if self.check_object_in_instruction(instruction, obj_name):
                    obj_involved.add(obj_id)
        
        pddl_problem = ''
        for s in problem_list:
            if not s:
                continue

            if " - object" in s or "GRASPABLE" in s or "CONTAINABLE" in s:
                trim = True
                for obj_id in obj_involved:
                    if obj_id in s:
                        trim = False
                        break
                if not trim:
                    pddl_problem += s + '\n'
            elif "close" in s:
                s_list = s.split()
                obj1_id = s_list[1]
                obj2_id = s_list[2].split(")")[0]

                if obj1_id in obj_involved and obj2_id in obj_involved:
                    pddl_problem += s + '\n'
            else:
                pddl_problem += s + '\n'
        return pddl_problem

    def revise_pddl_problem_definition(self, obj, e_recep, goal, pddl_problem_wo_goal):
        '''
        Revise object and init of PDDL problem based on llm output and form the complete pddl problem

        Args:
            obj: obj unique name in pddl init spec
            e_recep: end receptacle
            goal: goal spec
            pddl_problem_wo_goal: string
        Returns:
            pddl_problem: string
        '''
        # obj, s_recep, e_recep, goal = llm_output
        # # check if there is a need to add target object, start receptacle and end receptacle into problem
        # if obj in pddl_problem_wo_goal:
        #     obj = ""
        # if s_recep in pddl_problem_wo_goal:
        #     s_recep = ""
        # if e_recep in pddl_problem_wo_goal:
        #     e_recep = ""
        
        # problem_list = pddl_problem_wo_goal.split('\n')
        # pddl_problem = ""
        # for i, s in enumerate(problem_list):
        #     if "    (:objects " in s:
        #         pddl_problem += (s + '\n')

        #         if obj:
        #             pddl_problem += ("        " + obj + " - object\n")
        #         # if s_recep:
        #         #     pddl_problem += ("        " + s_recep + '\n')
        #         # if e_recep:
        #         #     pddl_problem += ("        " + e_recep + '\n')
        #     elif "    (:init " in s:
        #         pddl_problem += (s + '\n')

        #         if obj:
        #             pddl_problem += ("        (GRASPABLE " + obj + ')\n')
        #         # elif s_recep:
        #         #     pddl_problem += ("        (CONTAINABLE " + s_recep + ')\n')
        #         # elif e_recep:
        #         #     pddl_problem += ("        (CONTAINABLE " + e_recep + ')\n')
        #     # right bracket locates at the last 2 rather than the last 1
        #     elif i == len(problem_list) - 2:
        #         pddl_problem += (s + '\n')

        #         # insert goal specification
        #         goal_list = goal.split('\n')
        #         for sg in goal_list:
        #             if not sg:
        #                 continue
        #             pddl_problem += (' '*4 + sg + '\n')
                
        #         pddl_problem += "    (:metric minimize (total-cost))\n"
        #     else:
        #         pddl_problem += (s + '\n')

        pddl_problem = ""
        pddl_problem += "(define (problem pick_place_scenario)\n"
        pddl_problem += "    (:domain pick_and_place_nav)\n"
        # object
        pddl_problem += "    (:objects \n"
        pddl_problem += "        " + obj + " - object\n"
        pddl_problem += "        " + e_recep + " - object\n"
        pddl_problem += "        robo - robot\n"
        pddl_problem += "    )\n"
        # init
        pddl_problem += "    (:init\n"
        pddl_problem += "       (GRASPABLE " + obj + ")\n"
        pddl_problem += "       (CONTAINABLE " + e_recep + ")\n"
        pddl_problem += "       (free robo)\n"
        pddl_problem += "    )\n"
        # goal
        goal_list = goal.split('\n')
        for sg in goal_list:
            if not sg:
                continue
            pddl_problem += (' '*4 + sg + '\n')
        pddl_problem += "    (:metric minimize (total-cost))\n"
        pddl_problem += ")\n"

        return pddl_problem

    def search_obj_fur(self, obj_name, fur_name):
        '''
        Based on PDDL init spec, try to search for
        the edge whose two nodes (fur, obj) are the same
        as the given name

        Args:
            obj_name: object name
            fur_name: furniture name
        Returns:
            obj_id: object unique id in pddl problem
        '''
        problem_list = self.pddl_problem_wo_goal.split('\n')
        for line in problem_list:
            if "close" in line and obj_name in line and fur_name in line:
                line_list = line.split()
                obj_id = line_list[-1].split(")")[0]
                return obj_id
        return None

    def search_obj_over_pddl(self, obj_name):
        '''
        Based on PDDL init spec, search for the object
        with the same name

        Args:
            obj_name: object name
        Returns:
            obj_id: object unique id in pddl problem
        '''
        problem_list = self.pddl_problem_wo_goal.split('\n')
        for line in problem_list:
            if obj_name in line:
                line_list = line.split()
                obj_id = line_list[0]
                return obj_id

        return ""

    def reconstruct_pddl_problem_definition(self, pddl_init_spec, goal_spec, nonexist_objs):
        '''
        Construct the complete pddl problem definition for follow-up solver
        to plan the task

        Args:
            pddl_init_spec: string, initial pddl problem definition
            goal_spec: string, goal pddl problem definition
            nonexist_objs: [string], list of objects mentioned in instruction but not exist in initial problem def
        Returns:
            pddl_problem: string
        '''
        problem_list = pddl_init_spec.split('\n')
        problem_list = [s for s in problem_list if s]
        pddl_problem = ""
        for i, s in enumerate(problem_list):
            if "    (:objects " in s:
                pddl_problem += (s + '\n')

                for obj in nonexist_objs:
                    pddl_problem += ("        " + obj + " - object\n")
                # if s_recep:
                #     pddl_problem += ("        " + s_recep + '\n')
                # if e_recep:
                #     pddl_problem += ("        " + e_recep + '\n')
            elif "    (:init " in s:
                pddl_problem += (s + '\n')

                for obj in nonexist_objs:
                    pddl_problem += ("        (GRASPABLE " + obj + ')\n')
                # elif s_recep:
                #     pddl_problem += ("        (CONTAINABLE " + s_recep + ')\n')
                # elif e_recep:
                #     pddl_problem += ("        (CONTAINABLE " + e_recep + ')\n')
            # right bracket locates at the last 2 rather than the last 1
            elif i == len(problem_list) - 2:
                pddl_problem += (s + '\n')

                # insert goal specification
                goal_list = goal_spec.split('\n')
                for sg in goal_list:
                    if not sg:
                        continue
                    pddl_problem += (' '*4 + sg + '\n')
                
                pddl_problem += "    (:metric minimize (total-cost))\n"
            else:
                pddl_problem += (s + '\n')

        return pddl_problem

    def revise_raw_llm_output(self, llm_output):
        output_list = llm_output.split("\n")

        nonexist_objs = []
        revised_out = ""
        for s in output_list:
            if not s:
                continue

            s_list = s.split()
            
            if len(s_list) == 1:
                revised_out += (s + "\n")
                continue
            else:
                obj1_id = s_list[1]
                obj2_id = s_list[2].split(")")[0]

                if obj1_id in self.dict_pddlid_graphid:
                    s = s.replace(obj1_id, self.dict_pddlid_graphid[obj1_id])
                else:
                    nonexist_objs.append(obj1_id)
                if obj2_id in self.dict_pddlid_graphid:
                    s = s.replace(obj2_id, self.dict_pddlid_graphid[obj2_id])
                else:
                    nonexist_objs.append(obj2_id)
                revised_out  += (s + "\n")
        
        return revised_out, nonexist_objs

    def parse_llm_output(self, llm_output):
        '''
        Parse output from llm into a list of strings, format is [target object; start receptacle; end receptacle; goal spec]

        Args:
            llm_output: string
        Returns:
        '''
        output = []
        llm_output = llm_output.split("\n")
        target_object = ""
        start_receptacle = ""
        end_receptacle = ""
        goal_spec = ""
        reading_goal = False

        for i, line in enumerate(llm_output):
            if "1. target object:" in line.lower():
                target_object = line.split(': ')[1]
            elif "2. start receptacle:" in line.lower():
                start_receptacle = line.split(': ')[1]
            elif "3. end receptacle:" in line.lower():
                end_receptacle = line.split(': ')[1]
            elif "4. goal specification:" in line.lower():
                reading_goal = True
            elif reading_goal:
                if line.strip() == '':  # Assuming an empty line denotes the end of the goal specification
                    reading_goal = False  # Stop reading the goal specification
                else:
                    goal_spec += line + '\n'
            
            if not reading_goal and target_object and start_receptacle and end_receptacle and goal_spec:
                break

        return [target_object, start_receptacle, end_receptacle, goal_spec]

    def load_domain_definition(self):
        domain = ''
        with open(self.domain_file_path, 'r') as f:
            domain = f.read()
        
        return domain

    def write_pddl_problem(self, pddl_problem):
        with open(self.problem_file_path, 'w') as f:
            f.write(pddl_problem)

    def llm_output_postprocess(self, output_list):
        out = []

        i = 0
        # skip all other unrelated outputs
        while i < len(output_list):
            if output_list[i] and output_list[i][0] == "(":
                break
            i += 1

        while i < len(output_list):            
            out.append(output_list[i])
            i += 1
        
        return out

    def load_pddl_inital_problem(self):
        problem = ''
        path = os.path.join(self.current_file_path, '../config/initial_specification.pddl')

        # while not os.path.exists(path):
        #     with open(path, 'r') as f:
        #         problem = f.read()
        with open(path, 'r') as f:
            problem = f.read()


        # remove file
        # os.remove(path)
        return problem



    def pddl_solving(self):
        # call PDDL solver to solve written problem
        process_path = os.path.join(self.current_file_path, '../../../downward/fast-downward.py')
        subprocess.call(
            process_path + ' ' + self.domain_file_path + ' ' + self.problem_file_path + ' --search "lazy_greedy([ff()], preferred=[ff()])"',
            shell=True
        )
        
        # append plan to list
        plan = []
        if os.path.exists('./sas_plan'):
            with open('./sas_plan') as f:
                for i, line in enumerate(f.readlines()[:-1]):
                    # List of words in the current line of the sas_plan
                    elements = line.split('\n')[0]
                    elements = elements[1:-1].split()

                    plan.append(' '.join(elements))
            # delete file
            os.remove('./sas_plan')

            # save the solution
            with open(self.solution_path, 'w') as f:
                for sub_task in plan:
                    f.write(sub_task + '\n')
            
            return True
        else:
            return False
        

        

if __name__ == '__main__':
    self.instruction_callback()
