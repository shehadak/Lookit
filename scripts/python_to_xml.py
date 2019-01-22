import xml.etree.ElementTree as ET
import csv
import sys
import os
import json

class Trial():
	def __init__(self, number, responses ,prescreened_out=False, used=True):
		self.number=int(number)
		self.prescreened_out=prescreened_out
		self.responses=responses
		self.used=used
		if prescreened_out:
			self.used=False

	def __eq__(self,other):
		return(self.number==other.number)

	def __str__(self):
		and_or_but='and' if ((self.used) and (not self.prescreened_out)) or ((not self.used) and (self.prescreened_out)) else 'but'
		return("Trial number %i, %s %s %s." %(self.number, 'prescreened out' if self.prescreened_out else "not prescreened out",and_or_but, 'used' if self.used else 'unused'))
		
class Response():
	def __init__(self, ID, hour,minute,second,frame, trial, trial_status, Type, duration=""):
		self.ID = int(ID) if Type!='coding' else str(ID) # Response ID, starts from 1. (int)
		self.hour=int(hour) # Time of response in hours (int).
		self.second=int(second) # Time of response in hours (int).
		self.minute=int(minute) # Time of response in hours (int).
		self.frame=int(frame) # Time of response in hours (int).
		self.trial=int(trial) # Trial Number. (int)
		self.trial_status=bool(trial_status) # Trial Status. (boolean)
		self.Type=str(Type) # Trial Type: right, left, away, or off. (str)
		self.time=self.calculate_time()
		self.duration=duration

	def calculate_time(self):
		""" Calculates the time of the response in milliseconds.
			Returns time in milliseconds (int).
			"""
		Hours=int(self.hour)
		Minutes=int(self.minute)+60*Hours
		Seconds=int(self.second)+60*Minutes
		Frames=int(self.frame)+30*Seconds
		milliseconds=Frames*100/3
		return(milliseconds)

	def __str__(self):
		if self.Type=='coding':
			return('Response %s at hour: %i, minute: %i, second: %i, frame: %i, at trial %i, which is %s is at %s' %(self.ID,self.hour,self.minute,self.second,self.frame,self.trial,"active" if self.trial_status else "inactive",self.Type))
		else:
			return('Response %i at hour: %i, minute: %i, second: %i, frame: %i, at trial %i, which is %s is at %s' %(self.ID,self.hour,self.minute,self.second,self.frame,self.trial,"active" if self.trial_status else "inactive",self.Type))

	def __eq__(self,other):
		return(self.ID == other.ID and self.time==other.time and self.trial==other.trial and self.trial_status == other.trial_status and self.Type==other.Type)

def XMLDict_to_Pythondict(XML_Dict):
	""" Takes an XML dictionary (an XML object with the tag "dict")
		Returns a python dictionary mapping each key to its value in a python-readable form
		"""
	def array_to_list(array_item):
		l=[]
		for item in array_item:
			if item.tag=='dict':
				l.append(XMLDict_to_Pythondict(item))
			elif item.tag=='true' or item.tag=='false':
				l.append(item.tag)
			else:
				l.append(item.text)
		return(l)
	keys=[]
	values=[]
	for item in XML_Dict:
		if item.tag=='key':
			keys.append(item.text)
		elif item.tag=='dict':
			values.append(XMLDict_to_Pythondict(item))
		elif item.tag=='true' or item.tag=='false':
			values.append(item.tag)
		elif item.tag=='array':
			values.append(array_to_list(item))
		else:
			values.append(item.text)
	if len(keys)!=len(values):
		raise ValueError("Lengths are not equal")
	return({keys[i]:values[i] for i in range(len(keys))})

def extract_responses(tree):
	""" Takes a parsed XML (or vcx) file and extracts the important data
		Inputs: XML tree
		Returns: a dictionary on the form:
			{'Subject_info':dict mapping each attribute to its value, 'Responses': list of Response objects}
		"""
	main_dict=XMLDict_to_Pythondict(tree.getroot().find('dict'))
	Subject_data=main_dict['Subject']
	Responses=Subject_data['Responses']
	del Subject_data['Responses']
	organized_responses=[]
	for resp in Responses:
		trial_stat=True if Responses[resp]['Trial Status']=='true' else False
		curr_Resp=Response(int(resp.split(" ")[1]),
				Responses[resp]['Timecode']['Hour'],
				Responses[resp]['Timecode']['Minute'],
				Responses[resp]['Timecode']['Second'],
				Responses[resp]['Timecode']['Frame'],
				int(Responses[resp]['Trial']),
				trial_stat, Responses[resp]['Type'])
		organized_responses.append(curr_Resp)
	return({'Subject_info':Subject_data, 'Responses':sorted(organized_responses, key=lambda x: int(x.calculate_time()))})

def get_trials(Data, unused_trials=False):
	""" Takes a list of Respone objects and a boolean to indicate whether to include non-coded trials or not.
		Returns a dictionary mapping each trial number to a list fo its responses.
		"""
	def get_unused_trials(Data):
		prescreened_out_dict=Data['Subject_info']['Pre-Screen Information']['Pre-Screen Array 0']
		prescreened_out_list=[]
		for entry in prescreened_out_dict:
			prescreened_out_list.append(int(prescreened_out_dict[entry]['Trial']))
		return([Trial(int(t), [], used=False) for t in Data['Subject_info']['Unused Trials']]+[Trial(int(t), [], prescreened_out=True) for t in prescreened_out_list])
	total_trials={}
	Responses=Data['Responses']
	for res in Responses:
		if res.trial in total_trials:
			total_trials[res.trial].responses.append(res)
		else:
			total_trials[res.trial]=Trial(res.trial, [res])
	list_of_trials=list(total_trials.values())
	if unused_trials:
		for t in get_unused_trials(Data):
			list_of_trials.append(t)
	return(sorted(list_of_trials, key=lambda x:x.number))

def Response_duration(Responses, Response):
	""" Takes a list of Response objects and a specific Response object.
		Returns the duration of the specific Response object (i.e. the time difference between the response and the next response/next off).
		Raises an error if the response is not in the responses list, if the response type is "off", or if the trial_status of the response is Fasle.
		"""
	if Response not in Responses:
		raise ValueError("Response not in responses!")
	if Response.Type=="off":
		raise ValueError('Responses of type "off" do not have a duration.')
	if Response.trial_status==False:
		raise ValueError('Responses with inactive trial do not have a duration.')
	next_resp=Responses[Responses.index(Response)+1]
	return(abs(next_resp.time-Response.time))

def get_coding_duration(Data, Response):
	""" Measures the duration of the trial that begins with the given 'coding' response. This function is different from Response_duration() by that it measures
		the duration of the entire trial, instead of the duration of the time difference between the two subsequent responses.
		Takes a list of Response objects and a specific Response object of type "coding".
		Returns the duration of the trial that begins with the given response of type "coding".
		NOTE: Response must be of type coding, otherwise a ValueError apeears.
		"""
	# if Response.Type!="coding":
	# 	raise ValueError("Response must be of type 'coding'")
	# for i in range(Responses.index(Response)+1,len(Responses)):
	# 	if Responses[i].Type=='coding':
	# 		return round(abs(Responses[i].calculate_time()-Response.calculate_time()),2)
	# for tr in get_trials(Data, False):
	# 	coding_Event=tr[0] if tr[0].trial_status==1 else 2
	for trial in get_trials(Data, False):
		coding_event=trial.responses[0]
		if Response==coding_event:
			last_Event=trial.responses[-1]
			return(abs(last_Event.time-coding_event.time))



def get_total_time(Responses, types=[], trials=None, milliseconds=False):
	""" Takes a list of Response objects, a list of response types (e.g. ['left','right', 'away']), and a list of trial numbers.
		If given a list of trials, returns the amount of time of all the responses of the types specified in the trials specified.
		If not given a list of trials, returns the total amount of time of all the responses of the types specified in all trials.
		If milliseconds is True, returns total time in 30*seconds. Otherwise returns in seconds.
		"""
	if "off" in types:
		raise ValueError("Responses of type 'off' do not have a duration.")
	if trials==None:
		val=sum([Response_duration(Responses, Resp) for Resp in Responses if Resp.Type in types and Resp.trial_status])
		return val if milliseconds else round(val/30, 2)
	elif type(trials)==list:
		val=sum([Response_duration(Responses, Resp) for Resp in Responses if Resp.Type in types and Resp.trial in trials and Resp.trial_status])
		return val if milliseconds else round(val/30,2)
	else:
		raise ValueError("Trials must be entered as a list, even if only one trial")

def clean(Data):
	""" This functions takes some data and cleans it so that it is easily accessible by Python. Currently, the function does:
		- Given a Data dictionary in the form {'Subject_info': {...} , 'Responses': [...]}, it modifies the responses so that trials
			start and end with a 'coding' event according to their situation.
		Returns a Data dictionary in the form {'Subject_info': {...} , 'Responses': [...]}.
		"""
	copyData=Data.copy()
	Responses=copyData['Responses']
	if len(Responses)==0:
		return(copyData)
	# new_Responses=[Response("",Responses[0].hour,Responses[0].minute,Responses[0].second,Responses[0].frame,Responses[0].trial,False,'coding')]
	new_Responses=[]
	Trials=get_trials(copyData, False)
	# for i in range(len(Trials)): # I am using this form Trials.index(Trial(Responses[0].trial))+1 so that I do not consider the very first 'coding' event established in the previous two lines.
	# 	if i!=len(Trials)-1 and Trials[i].used and Trials[i+1].used:
	# 		similar_res=Trials[i].responses[-1]
	# 		new_Responses.append(Response("",similar_res.hour,similar_res.minute,similar_res.second,similar_res.frame,similar_res.trial+1,False,'coding'))
	# 	if i!= Trials.index(Trial(Responses[0].trial, [])) and Trials[i].used and not Trials[i-1].used:
	# 		similar_res=Trials[i].responses[0]
	# 		new_Responses.append(Response("",similar_res.hour,similar_res.minute,similar_res.second,similar_res.frame,similar_res.trial,False,'coding'))
	# The above commented lines were used to generate the coding event at the end of each trial.
	# TODO: delete the above commented files, if not needed.
	for trial in Trials:
		cur_res=trial.responses[0]
		new_Responses.append(Response("", trial.responses[0].hour, trial.responses[0].minute, trial.responses[0].second, trial.responses[0].frame, trial.responses[0].trial, False, 'coding'))
	Responses=new_Responses+Responses
	return({'Subject_info': copyData['Subject_info'] , 'Responses': sorted(Responses, key=lambda x:x.time)})

# tree=ET.parse('../raw_data/source_data/vcx/%s.vcx' %('trial_file'))
# Data=clean(extract_responses(tree))
# # for r in Data['Responses']:
# # 	print(r)
# for trial in (get_trials(Data, True)):
# 	print(trial)
# 	for r in trial.responses:
# 		print(r)

objects=[]
# vcx_dir='/Users/lookit/Desktop/Khaled-UROP/VM_to_PsychDS/V.M.-to-Psy-DS' # For Lab's mac
vcx_dir='/Users/shehada/Desktop/UROP/Psych-DS Project/vm to psychds/raw_data/source_data/vcx' # For my personal device.
with open('../raw_data/source_data/marchman_participants_data.tsv', 'w') as tsv_participants_file:
	# The marchman_participants_data.tsv file is opened this early so that we do not have to iterate over the sessions twice.
	for File in os.listdir(vcx_dir):
		if File[-4:]=='.vcx':
			## Exporting data from the vcx file.
			Filename=File[:-4]
			tree=ET.parse('../raw_data/source_data/vcx/%s.vcx' %(Filename))
			Data=clean(extract_responses(tree))

			## Dividing data into three subcategories: Responses_data, Session_level_data, and Trial_level_data. 
			Responses_data=Data['Responses'][:]
			Session_level_data=Data['Subject_info'].copy()
			Trial_level_data={'Pre-Screen Information':Session_level_data['Pre-Screen Information'], 'Unused Trials':Session_level_data["Unused Trials"]}
			del Session_level_data['Pre-Screen Information']
			del Session_level_data['Unused Trials']

			## Building the _timecourse_data.tsv file.
			with open('../raw_data/source_data/%s_timecourse_data.tsv' %(Filename), 'w') as tsv_timecourse_file:
			    tsv_writer = csv.writer(tsv_timecourse_file, delimiter='\t')
			    first_row=['Response', 'Hour', 'Minute', 'Second', 'Frame', 'Trial', 'Trial Status', 'Type', 'Duration']
			    objects+=first_row
			    tsv_writer.writerow(first_row) # First Row
			    for resp in Responses_data:
			    	if resp.Type=='coding':
			    		tsv_writer.writerow([str(resp.ID), str(resp.hour), str(resp.minute), str(resp.second), str(resp.frame), str(resp.trial), str(resp.trial_status), str(resp.Type),get_coding_duration(Data, resp)])
			    	else:	
			    		tsv_writer.writerow([str(resp.ID), str(resp.hour), str(resp.minute), str(resp.second), str(resp.frame), str(resp.trial), str(resp.trial_status), str(resp.Type),""])

			# Building the marchman_participants_data.tsv file.
			tsv_writer = csv.writer(tsv_participants_file, delimiter='\t')
			tsv_writer.writerow(['Number','Birthday','Sex','Months','Date of Test', 'Primary PS Complete', 'Primary Pre-Screener', 'Secondary PS Complete','Secondary PS Complete','Coded From','Coder', 'Checked By', 'Order'])
			tsv_writer.writerow([Session_level_data['Number'], Session_level_data['Birthday'], Session_level_data['Sex'], Session_level_data['Months'], Session_level_data['Date of Test'], Session_level_data['Primary PS Complete'], Session_level_data['Primary Pre-Screener'], Session_level_data['Secondary PS Complete'], Session_level_data['Secondary PS Complete'], Session_level_data['Coded From'], Session_level_data['Coder'], Session_level_data['Checked By'], Session_level_data['Order']])

			# Building the _trial_data.tsv.
