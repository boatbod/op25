#!/bin/sh

# op25_stats.sh -- 26 September 2017
# Copyright John Ackermann N8UR -- jra@febo.com
# Licensed under GNU General Public License V2 or later
#
# parse log file from op25 rx.py program
# and generate statistics.
#
# usage: op25_stats.sh logfile tsv_tagfile

# list of frequencies used
grep 'new freq:' $1 | cut -d" " -f4 | sort -n > op25-freqs-used.txt

# control channels used, and time of switch
grep 'set control channel:' $1 | cut -d" " -f1,5 > op25-cc-used.txt

# list of talkgroups used
grep 'new tgid:' $1 | cut -d" " -f4- | sort -n > op25-tgids-used.txt

# histogram of talkgroups
temp1=$(mktemp)
temp2=$(mktemp)
grep 'set tgid:' $1 | cut -d" " -f4- | sort -k1 | uniq -c \
    | sed -r 's/^ +([0-9]+) /\1\t/' > $temp1    # remove leading blanks
sort -k1 $2 > $temp2

# denominator for percentages
cmd_cnt=`grep 'set tgid:' $1 | wc -l` 

echo "# Talkgroup Frquency analysis" > op25-tgid-frequency.txt
echo "# PCT   Count   TGID    Description" >> op25-tgid-frequency.txt
join -1 2 -2 1 -a 1 -o 1.1,1.2,2.2,2.3,2.4,2.5,2.6,2.7,2.8,2.9,2.10,2.11,2.12,2.13 \
     $temp1 \
     $temp2 \
     | sort -nr \
     | sed 's/ /\t/' | sed 's/ /\t/' \
     | awk -v cmd_cnt="$cmd_cnt" \
         '{FS="\t"} {printf "%2.3f\t%d\t%d\t%s\n",($1/cmd_cnt)*100, $1, $2, $3}' \
     >> op25-tgid-frequency.txt

# histogram of unknown TGIDs
echo "Talkgroups without tags" > op25-tgids-tagless.txt
echo "# PCT   Count   TGID" >> op25-tgids-tagless.txt
grep 'Talkgroup' $1 | sort -k1 | uniq -c \
     | sort -nr \
     | sed 's/ /\t/' | sed 's/ /\t/' \
     | awk -v cmd_cnt="$cmd_cnt" \
         '{FS="\t"} {printf "%2.3f\t%d\t%d\n",($1/cmd_cnt)*100, $1, $2}' \
     >> op25-tgids-tagless.txt

# show activity (number of commands) per five minute interval
start=`grep 'set tgid:' $1 | head -n1 | cut -d" " -f1 | cut -c1-10`
echo "# Commands sent in prior 5 minutes (300 seconds)" > op25-activity.txt
echo "# Starting time (Unix epoch): $start" >> op25-activity.txt
echo "" >> op25-activity.txt
cut -c1-10 $1 | awk '{print int($1/300)}' | sort -n | uniq -c \
    | cut -d" " -f4- | sort -k2 -n \
    | awk '{if ($2 > 0) print $2*300,$1}' >> op25-activity.txt

