Nabaztag pairing proposal protocol
==================================

## States ##

Free
```
spouse_handle = None
spouse_state = None
```

Proposed
```
spouse_handle = "<proposed_peer>"
spouse_state = "proposed"
```

Waiting approval
```
spouse_handle = "<proposing_peer>"
spouse_state = "waiting_approval"
```

Married
```
spouse_handle = "<peer>"
spouse_state = "married"
```

## Messages ##

Parentheses and text in parentheses must be included in the message.

* Proposal

```(NabPairing Proposal - https://github.com/nabaztag2018/pynab)```

* Acceptation

```(NabPairing Acceptation - https://github.com/nabaztag2018/pynab)```

* Rejection

```(NabPairing Rejection - https://github.com/nabaztag2018/pynab)```

* Divorce

```(NabPairing Divorce - https://github.com/nabaztag2018/pynab)```

* Ears

```(NabPairing Ears <left> <right> - https://github.com/nabaztag2018/pynab)```

## Transitions ##

### Free

#### -> Proposed ####

| Events                              | Outputs                           |
|-------------------------------------|-----------------------------------|
| User enters the account of a peer   | A propose DM is sent to peer      |

#### -> Waiting approval ####

| Events                              | Outputs                           |
|-------------------------------------|-----------------------------------|
| Nabaztag receives a proposal DM     | Proposal choregraphy              |

#### -> Free ####

| Events                              | Outputs                                                |
|-------------------------------------|--------------------------------------------------------|
| Nabaztag receives an acceptation DM | A divorce DM is sent to peer                           |
| Nabaztag receives a rejection DM    | (none)                                                 |
| Nabaztag receives a divorce DM      | (none)                                                 |
| Nabaztag receives an ears DM        | A divorce DM is sent to peer                           |

### Proposed ###

#### -> Free ####

| Events                                    | Outputs                           |
|-------------------------------------------|-----------------------------------|
| User cancels the proposal                 | A divorce DM is sent to peer      |
| Nabaztag receives a matching rejection DM | Rejection choregraphy             |
| Nabaztag receives a matching divorce DM   | Rejection choregraphy             |

#### -> Married ####

| Events                                      | Outputs                                                |
|---------------------------------------------|--------------------------------------------------------|
| Nabaztag receives a matching acceptation DM | Wedding choregraphy                                    |
| Nabaztag receives a matching proposal DM    | Wedding choregraphy, an acceptation DM is sent to peer |

#### -> Proposed ####

| Events                                          | Outputs                           |
|-------------------------------------------------|-----------------------------------|
| Nabaztag receives a non-matching acceptation DM | A divorce DM is sent to peer      |
| Nabaztag receives a non-matching divorce DM     | (none)                            |
| Nabaztag receives a non-matching rejection DM   | (none)                            |
| Nabaztag receives a non-matching proposal DM    | A rejection DM is sent to peer    |
| Nabaztag receives a matching ears DM            | (none)                            |
| Nabaztag receives a non-matching ears DM        | A divorce DM is sent to peer      |

### Waiting approval ###

#### -> Married ####

| Events                              | Outputs                                                 |
|-------------------------------------|---------------------------------------------------------|
| User accepts the proposal           | Wedding choregraphy & An acceptation DM is sent to peer |

#### -> Free ####

| Events                                      | Outputs                                                    |
|---------------------------------------------|------------------------------------------------------------|
| User rejects the proposal                   | Rejection choregraphy (?) & A rejection DM is sent to peer |
| Nabaztag receives a matching divorce DM     | Divorce choregraphy (?)                                    |
| Nabaztag receives a matching rejection DM   | (none)                                                     |
| Nabaztag receives a matching acceptation DM | A divorce DM is sent to peer                               |

#### -> Waiting approval ####

| Events                                          | Outputs                                                        |
|-------------------------------------------------|----------------------------------------------------------------|
| Nabaztag receives a matching proposal DM        | Proposal choregraphy                                           |
| Nabaztag receives a non-matching proposal DM    | Proposal choregraphy & A rejection DM is sent to previous peer |
| Nabaztag receives a non-matching divorce DM     | (none)                                                         |
| Nabaztag receives a non-matching rejection DM   | (none)                                                         |
| Nabaztag receives a non-matching acceptation DM | A divorce DM is sent to peer                                   |
| Nabaztag receives a matching ears DM            | (none)                                                         |
| Nabaztag receives a non-matching ears DM        | A divorce DM is sent to peer                                   |

### Married ###

#### -> Free ####

| Events                                    | Outputs                                                |
|-------------------------------------------|--------------------------------------------------------|
| User breaks the wedding                   | Divorce choregraphy (?) & A divorce DM is sent to peer |
| Nabaztag receives a matching divorce DM   | Divorce choregraphy (?)                                |
| Nabaztag receives a matching rejection DM | Divorce choregraphy (?)                                |

### Married -> Married ###

| Events                                          | Outputs                                    |
|-------------------------------------------------|--------------------------------------------|
| Nabaztag receives a matching proposal DM        | An acceptation DM is sent to peer          |
| Nabaztag receives a matching acceptation DM     | (none)                                     |
| Nabaztag receives a matching ears DM            | Ears choregraphy + ears movement           |
| Nabaztag receives a non-matching proposal DM    | A rejection DM is sent to peer             |
| Nabaztag receives a non-matching acceptation DM | A divorce DM is sent to peer               |
| Nabaztag receives a non-matching rejection DM   | (none)                                     |
| Nabaztag receives a non-matching divorce DM     | (none)                                     |
| Nabaztag receives a non-matching ears DM        | A divorce DM is sent to peer               |
