from Arlo import Arlo

from datetime import timedelta, date
import datetime
import sys

USERNAME = 'trajan2-arlo@yahoo.de'
PASSWORD = 'FCBayern1900'

try:
    # Instantiating the Arlo object automatically calls Login(), which returns an oAuth token that gets cached.
    # Subsequent successful calls to login will update the oAuth token.
    arlo = Arlo(USERNAME, PASSWORD)
    # At this point you're logged into Arlo.

    today = (date.today()-timedelta(days=0)).strftime("%Y%m%d")
    seven_days_ago = (date.today()-timedelta(days=7)).strftime("%Y%m%d")

    # Get all of the recordings for a date range.
    library = arlo.GetLibrary(seven_days_ago, today)

    # Iterate through the recordings in the library.
    for recording in library:

        videofilename = datetime.datetime.fromtimestamp(
            int(recording['name'])//1000).strftime('%Y-%m-%d %H-%M-%S') + ' ' + recording['uniqueId'] + '.mp4'
        ##
        # The videos produced by Arlo are pretty small, even in their longest, best quality settings,
	    # but you should probably prefer the chunked stream (see below).
        ###
        #    # Download the whole video into memory as a single chunk.
        #    video = arlo.GetRecording(recording['presignedContentUrl'])
        #	 with open('videos/'+videofilename, 'wb') as f:
        #        f.write(stream)
        #        f.close()
        # Or:
        #
        # Get video as a chunked stream; this function returns a generator.
        stream = arlo.StreamRecording(recording['presignedContentUrl'])
        with open('videos/'+videofilename, 'wb') as f:
            for chunk in stream:
                f.write(chunk)
            f.close()

        print('Downloaded video '+videofilename+' from '+recording['createdDate']+'.')

    # Delete all of the videos you just downloaded from the Arlo library.
    # Notice that you can pass the "library" object we got back from the GetLibrary() call.
    # result = arlo.BatchDeleteRecordings(library)

    # If we made it here without an exception, then the videos were successfully deleted.
    print('Batch deletion of videos completed successfully.')

except Exception as e:
    print(e)
