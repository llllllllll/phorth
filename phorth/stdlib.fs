: 0< ( n -- f )
  0 < ;

: 0= ( n -- f )
  0 = ;

: 0> ( n -- f )
  0 > ;

: 2* ( n1 -- n2 )
  2 * ;

: 2+ ( n1 -- n2 )
  2 + ;

: 2- ( n1 -- n2 )
  2 - ;

: 2/ ( n1 -- n2 )
  2 / ;

: 2drop ( n1 n2 -- )
  drop drop ;

: 2dup ( n1 n2 -- n1 n2 n1 n2 )
  over over ;

: 1+ ( n -- n )
  1 + ;

: 1- ( n -- n )
  1 - ;

: ? ( adr -- )
  @ . ;

: nip ( n1 n2 -- n1 )
  swap drop ;

: noop ( -- )
  ;

: tuck ( n1 n2 -- n2 n1 n2 )
  dup -rot ;