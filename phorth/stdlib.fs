: 0< ( n -- f )
  0 < ;

: 0= ( n -- f )
  0 = ;

: 0> ( n -- f )
  0 > ;

: 1+ ( n -- n )
  1 + ;

: 1- ( n -- n )
  1 - ;

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

: ? ( adr -- )
  @ . ;

: noop ( -- )
  ;

: -rot ( n1 n2 n3 -- n3 n1 n2 )
  rot rot ;

: tuck ( n1 n2 -- n2 n1 n2 )
  dup rot ;
