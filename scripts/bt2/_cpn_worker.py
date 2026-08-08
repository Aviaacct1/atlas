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
  WHERE Origin IN ('ABE','ACV','ALB','AMA','ANC','ATL','ATY','AVL','BFL','BHM','BLI','BNA','BOS','BTV','BUF','BUR','BWI','BZN','CHA','CID','CLE','CLT','CMH','CVG','DAB','DAL','DCA','DEN','DFW','DRO','DSM','DTW','ECP','EGE','ELP','EUG','EWR','EYW','FAI','FAR','FCA','FLG','FLL','FNT','GRB','GRR','GSP','HNL','HOU','HRL','IAD','IAH','ICT','IND','ISP','JAC','JAX','LAS','LAX','LEX','LGA','LIT','LSE','MCI','MCO','MDT','MLB','MRY','MSP','MSY','MYR','OGG','OMA','ONT','ORD','ORF','PBI','PDX','PHL','PHX','PIT','PNS','PSP','PVD','RAP','RDD','RDM','RDU','RIC','RSW','SAN','SAV','SBA','SBP','SDF','SEA','SFO','SGU','SJC','SLC','SMF','SRQ','STS','SYR','TRI','TUL','TUS','TYS','VPS','XNA','YUM') AND Dest IN ('ABE','ACV','ALB','AMA','ANC','ATL','ATY','AVL','BFL','BHM','BLI','BNA','BOS','BTV','BUF','BUR','BWI','BZN','CHA','CID','CLE','CLT','CMH','CVG','DAB','DAL','DCA','DEN','DFW','DRO','DSM','DTW','ECP','EGE','ELP','EUG','EWR','EYW','FAI','FAR','FCA','FLG','FLL','FNT','GRB','GRR','GSP','HNL','HOU','HRL','IAD','IAH','ICT','IND','ISP','JAC','JAX','LAS','LAX','LEX','LGA','LIT','LSE','MCI','MCO','MDT','MLB','MRY','MSP','MSY','MYR','OGG','OMA','ONT','ORD','ORF','PBI','PDX','PHL','PHX','PIT','PNS','PSP','PVD','RAP','RDD','RDM','RDU','RIC','RSW','SAN','SAV','SBA','SBP','SDF','SEA','SFO','SGU','SJC','SLC','SMF','SRQ','STS','SYR','TRI','TUL','TUS','TYS','VPS','XNA','YUM') GROUP BY 1,2)
TO '{out}' (HEADER)'''.format(out=_os.path.join(_paths.AVIA, "bt2", "cpn_qtr_2019_4p2.csv.tmp"))
con.execute(q)
