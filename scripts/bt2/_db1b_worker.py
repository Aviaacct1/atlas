import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
from avia_forecast import paths as _paths
# The destination resolves through avia_forecast/paths.py. It was a literal
# /sessions/<name>/ path, so this worker could only ever run inside one Cowork
# session, and that session ended. Author: Avia Solutions.
import duckdb
con = duckdb.connect(); con.execute("SET memory_limit='3GB'; SET threads=8")
q = '''COPY (SELECT least(Origin,Dest) a, greatest(Origin,Dest) b,
  sum(try_cast(Passengers AS DOUBLE)) pax_sample
  FROM read_csv('/dev/stdin', header=true)
  WHERE try_cast(MktCoupons AS INT)=1 AND Origin IN ('AVL','BLI','BNA','BOI','BUR','BWI','BZN','CHA','CID','CLE','CLT','CVG','DAL','DFW','DSM','ELP','EWR','FLL','FNT','FWA','HPN','IND','JAX','JFK','KOA','LAS','LBB','LEX','LGA','MAF','MCI','MCO','MDT','MEM','MIA','MLB','MSN','MSY','MTJ','MYR','OAK','OKC','PDX','PHX','PIA','PIT','PNS','PWM','RDM','RNO','SAV','SBA','SFO','SJC','SMF','SNA','STL','TUS','TYS','VPS') AND Dest IN ('AVL','BLI','BNA','BOI','BUR','BWI','BZN','CHA','CID','CLE','CLT','CVG','DAL','DFW','DSM','ELP','EWR','FLL','FNT','FWA','HPN','IND','JAX','JFK','KOA','LAS','LBB','LEX','LGA','MAF','MCI','MCO','MDT','MEM','MIA','MLB','MSN','MSY','MTJ','MYR','OAK','OKC','PDX','PHX','PIA','PIT','PNS','PWM','RDM','RNO','SAV','SBA','SFO','SJC','SMF','SNA','STL','TUS','TYS','VPS') GROUP BY 1,2)
TO '{out}' (HEADER)'''.format(out=_os.path.join(_paths.AVIA, "bt2", "db1b_qtr_2016_4p2.csv.tmp"))
con.execute(q)
