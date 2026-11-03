"""Checked patch for EAX: never feed a capacity-truncated cycle set to Block2."""
from pathlib import Path


def apply_ab_cap_patch(directory):
    root = Path(directory)
    sources = {n: (root/n).read_text() for n in ('cross.cpp', 'cross.h', 'env.cpp', 'main.cpp')}
    def replace(name, old, new):
        if sources[name].count(old) != 1:
            raise RuntimeError('AB cap patch mismatch: ' + name + ': ' + old[:80])
        sources[name] = sources[name].replace(old, new)
    replace('cross.h', '  int fNumOfGeneratedCh;', '''  int fNumOfGeneratedCh;
  int fEffectiveEsetType; // 0=stop; 1=Single-AB; 2=complete Block2
  bool fABCapHit;
  bool fABAllowSingle;
  unsigned long fABCapHits;''')
    replace('cross.cpp', '  fN = N;', '''  fN = N;
  if( fMaxNumOfABcycle < 1 ){ fprintf(stderr, "invalid GA_MAXAB\\n"); exit(6); }
  const char* policy = getenv("GA_AB_CAP_POLICY");
  if( policy && strcmp(policy, "stop") && strcmp(policy, "single") ){
    fprintf(stderr, "invalid GA_AB_CAP_POLICY\\n"); exit(6);
  }
  fABAllowSingle = policy && !strcmp(policy, "single");
  if( fABAllowSingle && getenv("GA_FIXED_STAGE") && atoi(getenv("GA_FIXED_STAGE")) ){
    fprintf(stderr, "Single-AB fallback forbidden in a fixed-operator experiment\\n"); exit(6);
  }
  fABCapHit = false; fABCapHits = 0; fEffectiveEsetType = 0;''')
    replace('cross.cpp', '  fSPosi_ABL = 0;             // Large', '  fABCapHit = false;\n  fSPosi_ABL = 0;             // Large')
    original = '''  if( fNumOfABcycle == fMaxNumOfABcycle ){
    printf( "fMaxNumOfABcycle(%d) must be increased\\n", fMaxNumOfABcycle );
    exit( 1 );
  }'''
    # The base source must still contain its original guard. Never layer this
    # over an unknown replacement that silently ignores capacity.
    replace('cross.cpp', original, '''  if( fNumOfABcycle == fMaxNumOfABcycle ){
    // FormABcycle has completed; the remaining decomposition was not visited.
    fABCapHit = true;
  }''')
    replace('cross.cpp', '  this->SetABcycle( tPa1, tPa2, flagC, numOfKids );', '''  this->SetABcycle( tPa1, tPa2, flagC, numOfKids );
  fEffectiveEsetType = flagC[1];
  if( fABCapHit && flagC[1] == 2 ){
    ++fABCapHits;
    fEffectiveEsetType = fABAllowSingle ? 1 : 0;
    if( fABCapHits <= 4 || fABCapHits % 100 == 0 || !fABAllowSingle ){
      printf("ab_cap hits=%lu cycles=%d requested=2 effective=%d policy=%s\\n",
             fABCapHits, fNumOfABcycle, fEffectiveEsetType,
             fABAllowSingle ? "single" : "stop"); fflush(stdout);
    }
    if( !fABAllowSingle ) return;
  }''')
    replace('cross.cpp', '  if( flagC[ 1 ] == 2 ){           /* Block2 */',
            '  if( fEffectiveEsetType == 2 ){  /* Block2 requires a complete decomposition */')
    replace('cross.cpp', '  fEsetType = flagC[ 1 ];              /* 1:Single-AB, 2:Block2 */', '''  fEsetType = fEffectiveEsetType;
  if( fEsetType == 0 ){
    fprintf(stderr, "Block2 capacity reached; caller must checkpoint and stop\\n"); exit(5);
  }''')
    replace('cross.cpp', '    Num = fNumOfABcycle;', '''    Num = fNumOfABcycle;
  if( Num == 0 ){
    fNumOfGeneratedCh = 0;
    return; // Identical parents: no cycle, and no element zero to sort.
  }''')
    # Search_Eset sets this counter only for Block2. Single-AB must use the
    # selected cycle's A-edge count, not an uninitialized/stale Block2 value.
    replace('cross.cpp', '      fABcycleInEset[ fNumOfABcycleInEset++ ] = jnum;',
            '      fABcycleInEset[ fNumOfABcycleInEset++ ] = jnum;\n'
            '      fBest_Num_E = fABcycleL[ fPosi_ABL[jnum] ] / 2;')
    replace('env.cpp', '  tCross->SetParents( tCurPop[fIndexForMating[s]], tCurPop[fIndexForMating[s+1]], fFlagC, fNumOfKids );', '''  tCross->SetParents( tCurPop[fIndexForMating[s]], tCurPop[fIndexForMating[s+1]], fFlagC, fNumOfKids );
  if( tCross->fEffectiveEsetType == 0 ){
    // SetParents did not mutate the population; persist it before reporting failure.
    this->WriteCk("abcap");
    fprintf(stderr, "Block2 AB capacity reached; checkpoint saved, no truncated SetWeight\\n");
    exit(5);
  }''')
    # The imported main omitted InitSort. Calling a stateless method through
    # the global null pointer still has undefined behavior (caught by UBSAN).
    replace('main.cpp', '  InitURandom( atoi( argv[5] ) );',
            '  InitURandom( atoi( argv[5] ) );\n  if( !tSort ) InitSort();')
    # Validate every replacement before changing any file.
    for name, text in sources.items():
        (root/name).write_text(text)
