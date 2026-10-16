import json,sys,urllib.request
def ls(fid):
    req=urllib.request.Request("https://records.hawaiicounty.gov/WebLink/FolderListingService.aspx/GetFolderListing2",data=json.dumps({"repoName":"PublicDocuments","folderId":fid,"getNewListing":True,"start":0,"end":500,"sortColumn":"","sortAscending":True}).encode(),headers={"Content-Type":"application/json","User-Agent":"Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req,timeout=60))["data"]["results"]
if __name__=="__main__":
    for e in ls(int(sys.argv[1])): print(e["entryId"],e["type"],e["name"])
