import unittest
from unittest.mock import Mock,patch
import watch_quality as w

class WatchTests(unittest.TestCase):
    def test_only_matching_job_state(self):
        self.assertEqual(w.state_from('JobId=2878 JobState=RUNNING'), 'RUNNING')
        for text in ('JobId=28780 JobState=COMPLETED','JobId=2877 JobState=COMPLETED','JobId=2878'):
            with self.assertRaises(ValueError):w.state_from(text)

    def test_readonly_query_has_bounded_retry(self):
        query=Mock(side_effect=[RuntimeError('connection lost'),OSError('timeout'),'ok'])
        with patch.object(w.time,'sleep') as pause:
            self.assertEqual(w.readonly_retry(query),'ok')
        self.assertEqual(query.call_count,3)
        self.assertEqual([x.args[0] for x in pause.call_args_list],[5,10])
        query=Mock(side_effect=RuntimeError('offline'))
        with patch.object(w.time,'sleep'), self.assertRaises(RuntimeError):w.readonly_retry(query)
        self.assertEqual(query.call_count,3)

    def test_milestones_require_paired_complete(self):
        pair=lambda a,b:{'dense':{'verified_complete':a},'sparq':{'verified_complete':b}}
        r=dict(ppl=dict(modes=pair(True,False)),tasks={'piqa':dict(modes=pair(True,False))},complete=False)
        self.assertEqual(w.milestone_keys(r),[])
        r['ppl']['modes']=pair(True,True)
        self.assertEqual(w.milestone_keys(r),['ppl'])
        r['tasks']['piqa']['modes']=pair(True,True)
        self.assertEqual(w.milestone_keys(r),['ppl','piqa'])
        r['complete']=True
        self.assertEqual(w.milestone_keys(r),['ppl','piqa','quality_complete'])

if __name__=='__main__':unittest.main(verbosity=2)
