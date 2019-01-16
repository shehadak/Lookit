import xml.etree.ElementTree as ET
import csv
import sys
import os
class Session():
	def __init__(self, Subject_Number, Birthday, Sex, Months, Date_of_test, Prim_PS, Prim_PSer, Sec_PS, Sec_PSer, Coded_from, Coder, Checked_by, Order):
		self.Subject_Number=int(Subject_Number) # Subject ID (int).
		self.Birthday=str(Birthday) # Participant's birthday (str).
		self.Sex=bool(Sex) # Participant's sex: Male if true, Female if False (boolean).
		self.Months=int(Months) # Participant's age in months (int).
		self.Date_of_test=str(Date_of_test) # Date of test (str).
		self.Prim_PS=bool(Prim_PS) # Primary Prescreening Completed? (boolean).
		self.Sec_PS=bool(Sec_PS) # Secondary Prescreening Completed? (boolean).
		self.Prim_PSer=str(Prim_PSer) # Primary Prescreener (str).
		self.Sec_PSer=str(Sec_PSer) # Primary Prescreener (str).
		self.Coded_from=int(Coded_from) # The time coding started from (int).
		self.Coder=str(Coder) # Coder name/initials (str).
		self.Checked_by=str(Checked_by) # Name/Initials (str).
		self.Order=str(Order) # Order of session (str).

class Response():
	def __init__(self, ID, hour,minute,second,frame, trial, trial_status, Type):
		self.ID = int(ID) # Response ID, starts from 1. (int)
		self.hour=int(hour) # Time of response in hours (int).
		self.second=int(second) # Time of response in hours (int).
		self.minute=int(minute) # Time of response in hours (int).
		self.frame=int(frame) # Time of response in hours (int).
		self.trial=int(trial) # Trial Number. (int)
		self.trial_status=bool(trial_status) # Trial Status. (boolean)
		self.Type=str(Type) # Trial Type: right, left, away, or off. (str)
		self.time=self.calculate_time()

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
	first_trial=1
	for resp in Responses:
		trial_stat=True if Responses[resp]['Trial Status']=='true' else False
		if int(Responses[resp]['Trial'])<first_trial:
			first_trial=int(Responses[resp]['Trial'])
		curr_Resp=Response(len(organized_responses)+1,
				Responses[resp]['Timecode']['Hour'],
				Responses[resp]['Timecode']['Minute'],
				Responses[resp]['Timecode']['Second'],
				Responses[resp]['Timecode']['Frame'],
				int(Responses[resp]['Trial']),
				trial_stat, Responses[resp]['Type'])
		organized_responses.append(curr_Resp)
		if trial_stat==False:
			coding_Resp=Response(len(organized_responses)+1,
				Responses[resp]['Timecode']['Hour'],
				Responses[resp]['Timecode']['Minute'],
				Responses[resp]['Timecode']['Second'],
				Responses[resp]['Timecode']['Frame'],
				int(Responses[resp]['Trial']),
				trial_stat, 'coding')
	if len(organized_responses)>0:
		organized_responses.append(Response(1,0,0,0,0,first_trial,False,'coding'))
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
		return([int(t) for t in Data['Subject_info']['Unused Trials']]+prescreened_out_list)
	total_trials={}
	Responses=Data['Responses']
	for res in Responses:
		if res.trial_status:
			if res.trial in total_trials:
				total_trials[res.trial].append(res)
			else:
				total_trials[res.trial]=[res]
	if unused_trials:
		for t in get_unused_trials(Data):
			total_trials[t]=[]
	sorted_dict={}
	for k in sorted(total_trials.keys()):
		sorted_dict[k]=total_trials[k]
	return(sorted_dict)

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

def get_coding_duration(Responses, Response):
	""" Measures the duration of the trial that begins with the given 'coding' response. This function is different from Response_duration() by that it measures
		the duration of the entire trial, instead of the duration of the time difference between the two subsequent responses.
		Takes a list of Response objects and a specific Response object of type "coding".
		Returns the duration of the trial that begins with the given response of type "coding".
		NOTE: Response must be of type coding, otherwise a ValueError apeears.
		"""
	if Response.Type!="coding":
		raise ValueError("Response must be of type 'coding'.")
	for i in range(Responses.index(Response)+1,len(Responses)):
		if Responses[i].type=='coding':
			return abs(Responses[i].calculate_time()-Response.calculate_time())

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


tree=ET.parse('../%s.vcx' %('trial_file'))
Data=extract_responses(tree)
for i in Data['Responses']:
	print(i)


# vcx_dir='/Users/lookit/Desktop/Khaled-UROP/VM_to_PsychDS/V.M.-to-Psy-DS'
# for File in os.listdir(vcx_dir):
# 	if File[-4:]=='.vcx':
# 		## Exporting data from the vcx file.
# 		Filename=File[:-4]
# 		tree=ET.parse('../%s.vcx' %(Filename))
# 		Data=extract_responses(tree)

# 		## Dividing data into three subcategories: Responses_data, Session_level_data, and Trial_level_data. 
# 		Responses_data=Data['Responses'][:]
# 		Session_level_data=Data['Subject_info'].copy()
# 		Trial_level_data={'Pre-Screen Information':Session_level_data['Pre-Screen Information'], 'Unused Trials':Session_level_data["Unused Trials"]}
# 		del Session_level_data['Pre-Screen Information']
# 		del Session_level_data['Unused Trials']

# 		## Building the _timecourse_data.tsv file.
# 		with open('../raw_data/source_data/%s_timecourse_data.tsv' %(Filename), 'w') as tsv_file:
# 		    tsv_writer = csv.writer(tsv_file, delimiter='\t')
# 		    tsv_writer.writerow(['Response', 'Hour', 'Minute', 'Second', 'Frame', 'Trial', 'Trial Status', 'Type', 'Duration']) # First Row
# 		    for resp in Responses_data:
# 		    	if resp.Type=='coding':
# 		    		tsv_writer.writerow([str(resp.ID), str(resp.hour), str(resp.minute), str(resp.frame), str(resp.trial), str(resp.trial_status), str(resp.Type),get_coding_duration(Responses, resp)])
# 		    	else:	
# 		    		tsv_writer.writerow([str(resp.ID), str(resp.hour), str(resp.minute), str(resp.frame), str(resp.trial), str(resp.trial_status), str(resp.Type),""])

# 		## Building the marchman_participants_data.tsv file.
# 		# with open('../raw_data/source_data/marchman_participants_data.tsv'):
# 		# 	Session(self, Subject_Number, Birthday, Sex, Months, Date_of_test, Prim_PS, Prim_PSer, Sec_PS, Sec_PSer, Coded_from, Coder, Checked_by, Order)



