import discord
import asyncio
import datetime
import json
import os

client = discord.Client()

file_path = os.path.dirname(__file__)
config_path = os.path.join(file_path, 'config.json')
config_data = json.load(open(config_path))

#Checks for log folder, creates it if absent
log_folder = os.path.join(file_path, ' logs')
folder_exists = os.path.isdir(log_folder)
if not folder_exists:
  os.mkdir(log_folder)

#Create user list dictionary
user_path = os.path.join(log_folder, 'userlog.txt')
userlog_exists = os.path.isfile(user_path)
if not userlog_exists:
  with open(user_path, 'a'):
    pass
user_file = open(user_path, 'r')
user_dict = {}
for line in user_file:
    k, v = line.strip().split(',')
    user_dict[k.strip()] = v.strip()

user_file.close()

#Create ban list dictionary
ban_path = os.path.join(log_folder, 'banlog.txt')
banlog_exists = os.path.isfile(ban_path)
if not banlog_exists:
  with open(ban_path, 'a'):
    pass
current_bans_file = open(ban_path, 'r')
current_bans_dict = {}
for line in current_bans_file:
    k, v = line.strip().split(',')
    user_dict[k.strip()] = v.strip()

current_bans_file.close()


#Print login details
@client.async_event
async def on_ready():
  print('Logged in as')
  print('\nLogged in to servers:')
  for server in client.servers:
    print(server.name)
  print(config_data["botID"])
  print('------')

#Write messages to daily log file
#def log_command(message, text, error=False)


#Detect message to the bot
#Parameters: Message object
#Return: void
@client.async_event
async def on_message(message):
  
  #Check if the message is connected to a server, or from the bot itself
  if message.server is None and not message.author.bot:
    
    #Votekick initiation check
    if message.content.startswith('!votekick '):
      await client.send_message(message.channel, f"Beginning Process")
      
      #Get the username from the votekick command
      username = message.content.replace("!votekick ", "")
      await client.send_message(message.channel, f"Given username = {username}")
      
      #Get the active server, to be moved to a config file at a later time for easier editing
      active_server = config_data["serverID"]
      
      #Grab message sender, their relevant voice channel and all members in said channel
      active_user = active_server.get_member(message.author.id)
      voice_channel = active_user.voice.voice_channel
      voice_channel_members = voice_channel.voice_members
      
      #Check if the channel is on votekick cooldown
      if voice_channel.id in current_bans_dict:
        await client.send_message(message.channel, f"Channel {voice_channel.name} is on cooldown")
      else:
        #Call the check_for_member method, returning a member or an empty string
        member_to_be_kicked = await check_for_member(username, voice_channel, message)

        #INverse check for if the return is an empty string 
        if member_to_be_kicked != "":

          #Minimum required members is 3, if less then skip
          if len(voice_channel_members) >= 3:
            await client.send_message(message.channel, f"Initiating Vote Kick")

            #Await the votekick method to complete
            await vote_kick(message, voice_channel, member_to_be_kicked)
            await client.send_message(message.channel, f"Process Complete")
          else:
            await client.send_message(message.channel, f"{voice_channel.name} contains less than 3 users")
        else:
          await client.send_message(message.channel, f"{voice_channel.name} does not contain that member")
      #elif message.content.startswith('!sleep'):
        #await asyncio.sleep(5)
        #await client.send_message(message.channel, 'Done sleeping')
      
#Iniates a votekick process, creating a task pool to dm all members except the target
#Parameters: Message object, Channel object, Member object
#Returns: void
async def vote_kick(message, voice_channel, member_to_be_kicked):
  
  #The votes needed is equal to the total count of members minus the targetted member
  vote_needed = len(voice_channel.voice_members) - 1
  await client.send_message(message.channel, f"Vote needed is {vote_needed}")
  
  #Initialise vote count and list of users to vote
  vote_count = 0
  user_list = []
  
  #Check if each member is the taggetted member, if not add the user to the list
  for member in voice_channel.voice_members:
    if member != member_to_be_kicked:
      user = await client.get_user_info(member.id)
      user_list.append(user)
      
  #Create a task list for each user in users list, then gather all tasks and await running completion
  tasks = [request_vote(message, user, member_to_be_kicked) for user in user_list]
  async_run = asyncio.gather(*tasks)
  await asyncio.ensure_future(async_run)
  
  #Iterate all returns, and check vote total result
  for task_result in async_run.result():
    vote_count += task_result
  if vote_count >= vote_needed:
    await client.send_message(message.channel, f"Vote passed")
    
    #Create a channel from the designated ID, then move the user to said channel. ID to be added to config
    dump_channel = config_data["channelID"]
    await client.move_member(member_to_be_kicked, dump_channel)
    
    #Add a ban to the channel in question for that user
    overwrite = discord.PermissionOverwrite()
    overwrite.connect = False
    await client.edit_channel_permissions(voice_channel, member_to_be_kicked, overwrite)

    #Add cooldown to the current voice channel
    current_bans_dict[voice_channel.id] = datetime.datetime.now()
  else:
    await client.send_message(message.channel, f"Vote failed")
  await client.send_message(message.channel, f"Kick Complete")
  
#Send a DM to a user, requesting a reaction to a message within 60 seconds
#Parameters: Message object, User object, Member object
#Returns: int
async def request_vote(message, user_voting, member_to_be_kicked):
  
  #Sends the DM to the user, then adds two reactions. To be added to config
  votekick_message = await client.send_message(user_voting, f"Would you like to kick {member_to_be_kicked.name}?")
  await client.add_reaction(votekick_message, "\U00002705")
  await client.add_reaction(votekick_message, "\U0000274E")
  
  #Waits for reaction, timesout in 60 seconds. Returns 0 or 1 depending on result
  vote_check = await client.wait_for_reaction(emoji=["\U00002705","\U0000274E"], user=user_voting, timeout=60, message=votekick_message)
  await client.delete_message(votekick_message)
  if vote_check == "None":
    return 0
  else:
    await client.send_message(message.channel, f"{user_voting.name} has selected {vote_check.reaction.emoji}")
    
    #Increase the user's vote count in the dictionary
    username = f"{user_voting.name}#{user_voting.discriminator}"
    if username in user_dict:
      user_dict[username] += 1
    else:
      user_dict[username] = 1
    if vote_check.reaction.emoji == "\U00002705":
      return 1
    elif vote_check.reaction.emoji == "\U0000274E":
      return 0
    
def get_countdown_string(timedelta_object):
  """Given a timedelta object, returns a mm:ss time string"""
  countdown_timer_split = str(timedelta_object).split(":")
  countdown_timer_string = ":".join(countdown_timer_split[1:])
  return countdown_timer_string.split(".")[0]  # Without decimal

#Checks if the given member exists within the voice channel
#Parameters: string, Channel object, Message object
#Returns: Member object or string
async def check_for_member(username, voice_channel, message):
  
  #Iterate through each member in the voice channel, gathering their full username and discriminator,
  #then comparing to the given username
  for member in voice_channel.voice_members:
    member_username = f"{member.name}#{member.discriminator}"
    await client.send_message(message.channel, f"Member username = {member_username}")
    if username == member_username:
      
      #Return the member if a positive match
      await client.send_message(message.channel, f"Found member")
      return member
    
  #If no match is found, return empty string
  return ""

client.run(config_data["botToken"])