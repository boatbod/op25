/*
 * (C) 2019, Graham J Norbury
 *           gnorbury@bondcar.com
 *
 * Stand-alone utility to scan a binary dibit file and look for
 * various sync sequences.  Can match with up to 6 bit errors
 *
 */

#include <stdio.h>
#include <stdint.h>
#include <fstream>

static const uint64_t DMR_BS_VOICE_SYNC_MAGIC      = 0x755fd7df75f7LL;
static const uint64_t DMR_BS_DATA_SYNC_MAGIC       = 0xdff57d75df5dLL;
static const uint64_t DMR_MS_VOICE_SYNC_MAGIC      = 0x7f7d5dd57dfdLL;
static const uint64_t DMR_MS_DATA_SYNC_MAGIC       = 0xd5d7f77fd757LL;
static const uint64_t DMR_MS_RC_SYNC_MAGIC         = 0x77d55f7dfd77LL;
static const uint64_t DMR_T1_VOICE_SYNC_MAGIC      = 0x5d577f7757ffLL;
static const uint64_t DMR_T1_DATA_SYNC_MAGIC       = 0xf7fdd5ddfd55LL;
static const uint64_t DMR_T2_VOICE_SYNC_MAGIC      = 0x7dffd5f55d5fLL;
static const uint64_t DMR_T2_DATA_SYNC_MAGIC       = 0xd7557f5ff7f5LL;
static const uint64_t DSTAR_FRAME_SYNC_MAGIC       = 0x444445101440LL; 
static const uint64_t P25_FRAME_SYNC_MAGIC         = 0x5575F5FF77FFLL;
static const uint64_t P25P2_FRAME_SYNC_MAGIC       = 0x575D57F7FFLL;   // only 40 bits

static const int          SYNC_SIZE		   = 48; // 48 bits
static const unsigned int SYNC_THRESHOLD	   = 6;  // up to 6 bit errorss
static const unsigned int SYNC_MAGICS_COUNT    = 11;
static const uint64_t     SYNC_MAGICS[]        = {DMR_BS_VOICE_SYNC_MAGIC,
                                                  DMR_BS_DATA_SYNC_MAGIC,
                                                  DMR_MS_VOICE_SYNC_MAGIC,
                                                  DMR_MS_DATA_SYNC_MAGIC,
                                                  DMR_MS_RC_SYNC_MAGIC,
                                                  DMR_T1_VOICE_SYNC_MAGIC,
                                                  DMR_T1_DATA_SYNC_MAGIC,
                                                  DMR_T2_VOICE_SYNC_MAGIC,
                                                  DMR_T2_DATA_SYNC_MAGIC,
                                                  DSTAR_FRAME_SYNC_MAGIC,
						 P25_FRAME_SYNC_MAGIC};
static const char         SYNCS[][25]          = {"DMR_BS_VOICE_SYNC",
                                                  "DMR_BS_DATA_SYNC",
                                                  "DMR_MS_VOICE_SYNC",
                                                  "DMR_MS_DATA_SYNC",
                                                  "DMR_MS_RC_SYNC",
                                                  "DMR_T1_VOICE_SYNC",
                                                  "DMR_T1_DATA_SYNC",
                                                  "DMR_T2_VOICE_SYNC",
                                                  "DMR_T2_DATA_SYNC",
						  "DSTAR_FRAME_SYNC",
						  "P25_FRAME_SYNC"};

bool test_sync(uint64_t cw, int &sync, int &errs)
{
	int popcnt = 0;
	for (int i = 0; i < SYNC_MAGICS_COUNT; i ++)
	{
        	popcnt = __builtin_popcountll(cw ^ SYNC_MAGICS[i]);
		if (popcnt <= SYNC_THRESHOLD)
		{
			sync = i;
			errs = popcnt;
                	return true;
                }
        }

	return false;
}

int main (int argc, char* argv[])
{
	uint64_t cw = 0;
	int sync = 0;
	int s_errs = 0;
	
	if (argc < 2)
	{
		fprintf(stderr, "Usage: scan4sync <filename>\n");
		return 1;
	}

	char dibit;
	size_t fpos = 0;
	std::fstream file(argv[1], std::ios::in | std::ios::binary);
	while (!file.eof())
	{
		file.read((&dibit), 1);
		fpos++;

		cw = ((cw << 1) + ((dibit >>1) & 0x1)) & 0xffffffffffff;
		if (test_sync(cw, sync, s_errs))
			printf("%s [%06lx] matched [%06lx] with %d errs at %lu bit 1\n", SYNCS[sync], SYNC_MAGICS[sync], cw, s_errs, fpos);

		cw = ((cw << 1) + (dibit & 0x1)) & 0xffffffffffff;
		if (test_sync(cw, sync, s_errs))
			printf("%s [%06lx] matched [%06lx] with %d errs at %lu bit 0\n", SYNCS[sync], SYNC_MAGICS[sync], cw, s_errs, fpos);

	}

    return 0;

}

